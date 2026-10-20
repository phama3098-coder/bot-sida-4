"""
VietPhotoBooth FastAPI Application Server
Provides REST APIs, Server-Sent Events, MJPEG Live View, and Web Touch UI.
"""

import os
import io
import time
from typing import Dict, Any, Optional
from fastapi import FastAPI, Request, Response, Form, Query, HTTPException, status
from fastapi.responses import HTMLResponse, StreamingResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from vietphotobooth.core.config import ConfigManager
from vietphotobooth.core.events import EventManager
from vietphotobooth.core.logger import get_logger
from vietphotobooth.core.state_machine import SessionManager
from vietphotobooth.camera.manager import CameraManager
from vietphotobooth.camera.compatibility import get_compatibility_records
from vietphotobooth.processing.template_engine import TemplateEngine
from vietphotobooth.printing.manager import PrintManager
from vietphotobooth.printing.dnp_rx1hs import DNPRX1HSProfile
from vietphotobooth.sharing.token_manager import TokenManager

logger = get_logger()

def create_app() -> FastAPI:
    app = FastAPI(title="VietPhotoBooth Server", version="1.0.0")

    # Khởi tạo các singleton manager
    config = ConfigManager()
    event_mgr = EventManager(storage_root=config.get("storage_dir"), current_event=config.get("current_event"))
    camera_mgr = CameraManager(default_backend=config.get("camera_backend", "simulator"), device_index=config.get("camera_device_index", 0))
    template_engine = TemplateEngine(templates_dir=os.path.join(config.get("storage_dir"), "Templates"))
    print_mgr = PrintManager(default_printer=config.get("printer_name", ""))
    token_mgr = TokenManager(port=int(config.get("lan_server_port", 8080)))

    session_mgr = SessionManager(
        config=config,
        event_mgr=event_mgr,
        camera_mgr=camera_mgr,
        template_engine=template_engine,
        print_mgr=print_mgr,
        token_mgr=token_mgr
    )

    # Thư mục UI
    base_dir = os.path.dirname(os.path.abspath(__file__))
    ui_dir = os.path.join(base_dir, "ui")
    templates_dir = os.path.join(ui_dir, "templates")
    static_dir = os.path.join(ui_dir, "static")

    os.makedirs(templates_dir, exist_ok=True)
    os.makedirs(static_dir, exist_ok=True)

    templates = Jinja2Templates(directory=templates_dir)
    app.mount("/static", StaticFiles(directory=static_dir), name="static")

    # ==========================
    # GIAO DIỆN WEB CHÍNH
    # ==========================

    @app.get("/", response_class=HTMLResponse)
    async def kiosk_view(request: Request):
        """Màn hình cảm ứng Photobooth Kiosk cho khách chụp ảnh."""
        return templates.TemplateResponse(
            request=request,
            name="index.html",
            context={
                "event_title": config.get("event_title", "Kỷ Niệm Ngày Cưới"),
                "event_subtitle": config.get("event_subtitle", "Chúc Mừng Hạnh Phúc"),
                "event_date": config.get("event_date", "2026-10-20"),
                "countdown_seconds": config.get("countdown_seconds", 5),
                "current_event": event_mgr.current_event
            }
        )

    @app.get("/admin", response_class=HTMLResponse)
    async def admin_view(request: Request):
        """Trang quản trị hệ thống Photobooth với 10 phân hệ chức năng."""
        return templates.TemplateResponse(
            request=request,
            name="admin.html",
            context={
                "config": config.all,
                "current_event": event_mgr.current_event,
                "printers": print_mgr.get_printers(),
                "selected_printer": print_mgr.get_selected_printer(),
                "camera_info": camera_mgr.get_info()
            }
        )

    @app.get("/s/{token}", response_class=HTMLResponse)
    async def guest_share_view(request: Request, token: str):
        """Trang xem và tải ảnh trên điện thoại của khách quét mã QR mạng nội bộ."""
        share_obj = token_mgr.get_token(token)
        if not share_obj:
            return templates.TemplateResponse(
                request=request,
                name="guest.html",
                context={
                    "error": "Đường dẫn chia sẻ đã hết hạn hoặc bị thu hồi bởi quản trị viên."
                }
            )
        return templates.TemplateResponse(
            request=request,
            name="guest.html",
            context={
                "token": token,
                "filename": share_obj.filename,
                "event_name": share_obj.event_name,
                "created_at": datetime.fromtimestamp(share_obj.created_at).strftime("%H:%M %d/%m/%Y"),
                "wifi_ip": token_mgr.get_local_ip()
            }
        )

    # ==========================
    # API PHIÊN CHỤP (SESSION)
    # ==========================

    @app.get("/api/session/status")
    async def get_session_status():
        return session_mgr.get_status()

    @app.post("/api/session/start")
    async def start_session():
        return session_mgr.start_session()

    @app.post("/api/session/cancel")
    async def cancel_session():
        return session_mgr.cancel_session()

    @app.post("/api/session/reset")
    async def reset_session():
        return session_mgr.reset_to_idle()

    @app.post("/api/session/print")
    async def print_session_photo(copies: int = Form(1)):
        return session_mgr.trigger_print(copies=copies)

    # ==========================
    # API LIVE VIEW (STREAMING)
    # ==========================

    @app.get("/api/camera/liveview")
    def liveview_stream():
        """Luồng phát video Live View chuẩn MJPEG (Motion JPEG)."""
        def generate():
            while True:
                frame_bytes = camera_mgr.get_liveview()
                if frame_bytes:
                    yield (b"--frame\r\n"
                           b"Content-Type: image/jpeg\r\n\r\n" + frame_bytes + b"\r\n")
                time.sleep(0.04)  # ~25 FPS

        return StreamingResponse(
            generate(),
            media_type="multipart/x-mixed-replace; boundary=frame"
        )

    # ==========================
    # API MÁY ẢNH (CAMERA)
    # ==========================

    @app.get("/api/camera/info")
    async def get_camera_info():
        return camera_mgr.get_info()

    @app.get("/api/camera/devices")
    async def get_camera_devices():
        return camera_mgr.detect_all_devices()

    @app.post("/api/camera/switch")
    async def switch_camera(backend: str = Form(...), device_index: int = Form(0)):
        success = camera_mgr.switch_backend(backend, device_index)
        if success:
            config.set("camera_backend", backend)
            config.set("camera_device_index", device_index)
            config.save()
        return {"success": success, "backend": backend, "device_index": device_index}

    @app.get("/api/camera/compatibility")
    async def get_camera_compatibility(query: str = ""):
        return get_compatibility_records(query)

    # ==========================
    # API MÁY IN (PRINTER)
    # ==========================

    @app.get("/api/printer/list")
    async def get_printers_list():
        return {
            "printers": print_mgr.get_printers(),
            "selected_printer": print_mgr.get_selected_printer()
        }

    @app.post("/api/printer/select")
    async def select_printer(printer_name: str = Form(...)):
        success = print_mgr.set_selected_printer(printer_name)
        if success:
            config.set("printer_name", printer_name)
            config.save()
        return {"success": success, "selected_printer": printer_name}

    @app.get("/api/printer/queue")
    async def get_print_queue():
        return print_mgr.get_queue()

    @app.post("/api/printer/cancel")
    async def cancel_print_job(job_id: str = Form(...)):
        return {"success": print_mgr.cancel_job(job_id)}

    @app.post("/api/printer/retry")
    async def retry_print_job(job_id: str = Form(...)):
        return {"success": print_mgr.retry_job(job_id)}

    @app.post("/api/printer/test")
    async def test_print():
        """Tạo thẻ in thử nghiệm và gửi tới máy in được chọn."""
        dirs = event_mgr.get_current_dirs()
        test_path = os.path.join(dirs["final"], f"test_card_{int(time.time())}.jpg")
        print_mgr.create_test_print_card(test_path)
        job = print_mgr.submit_job(image_path=test_path, copies=1, paper_size="4x6", event_name="Test")
        return {"success": True, "job_id": job.job_id, "image_path": test_path}

    @app.get("/api/printer/dnp-guide")
    async def get_dnp_guide():
        return DNPRX1HSProfile.get_hardware_guidelines()

    # ==========================
    # API TEMPLATES
    # ==========================

    @app.get("/api/templates")
    async def list_templates():
        return {
            "templates": template_engine.list_templates(),
            "selected_template": config.get("template_id", "strip_2x6_3photos")
        }

    @app.post("/api/templates/select")
    async def select_template(template_id: str = Form(...)):
        config.set("template_id", template_id)
        config.save()
        return {"success": True, "selected_template": template_id}

    # ==========================
    # API QUẢN LÝ SỰ KIỆN
    # ==========================

    @app.get("/api/events")
    async def list_events():
        return {
            "events": event_mgr.list_events(),
            "current_event": event_mgr.current_event,
            "disk_status": event_mgr.check_disk_space(float(config.get("disk_warning_gb", 2.0)))
        }

    @app.post("/api/events/create")
    async def create_event(name: str = Form(...)):
        success = event_mgr.create_event(name)
        return {"success": success, "event_name": name}

    @app.post("/api/events/switch")
    async def switch_event(name: str = Form(...)):
        success = event_mgr.set_active_event(name)
        if success:
            config.set("current_event", name)
            config.save()
        return {"success": success, "current_event": name}

    @app.post("/api/events/rename")
    async def rename_event(old_name: str = Form(...), new_name: str = Form(...)):
        success = event_mgr.rename_event(old_name, new_name)
        if success and config.get("current_event") == old_name:
            config.set("current_event", new_name)
            config.save()
        return {"success": success}

    @app.get("/api/events/export/{event_name}")
    async def export_event_zip(event_name: str):
        dirs = event_mgr.get_current_dirs()
        zip_path = os.path.join(dirs["root"], f"{event_name}_backup.zip")
        success = event_mgr.export_event_zip(event_name, zip_path)
        if success and os.path.exists(zip_path):
            return FileResponse(zip_path, filename=f"{event_name}_export.zip", media_type="application/zip")
        raise HTTPException(status_code=404, detail="Không thể tạo file xuất sự kiện.")

    # ==========================
    # API THƯ VIỆN ẢNH (GALLERY)
    # ==========================

    @app.get("/api/gallery")
    async def get_gallery(event: str = ""):
        target_event = event or event_mgr.current_event
        event_path = event_mgr.get_event_path(target_event)
        final_dir = os.path.join(event_path, "Final")
        photos = []
        if os.path.exists(final_dir):
            for f in sorted(os.listdir(final_dir), reverse=True):
                if f.lower().endswith(('.jpg', '.jpeg', '.png')):
                    fp = os.path.join(final_dir, f)
                    photos.append({
                        "filename": f,
                        "size_kb": round(os.path.getsize(fp) / 1024, 1),
                        "created_at": datetime.fromtimestamp(os.path.getctime(fp)).strftime("%Y-%m-%d %H:%M:%S")
                    })
        return {"event": target_event, "photos": photos}

    @app.get("/api/photo/{category}/{filename}")
    async def serve_photo(category: str, filename: str, event: str = ""):
        """Phục vụ ảnh an toàn chống path traversal."""
        safe_filename = os.path.basename(filename)
        target_event = event or event_mgr.current_event
        event_path = event_mgr.get_event_path(target_event)

        cat_folder = "Final" if category == "final" else "Thumbnails" if category == "thumb" else "Originals"
        target_path = os.path.join(event_path, cat_folder, safe_filename)

        if os.path.exists(target_path):
            return FileResponse(target_path, media_type="image/jpeg")
        raise HTTPException(status_code=404, detail="Không tìm thấy ảnh.")

    # ==========================
    # API CHIA SẺ MẠNG LAN & QR
    # ==========================

    @app.get("/api/sharing/tokens")
    async def get_sharing_tokens():
        return token_mgr.list_tokens()

    @app.post("/api/sharing/revoke")
    async def revoke_token(token: str = Form(...)):
        return {"success": token_mgr.revoke_token(token)}

    @app.get("/api/sharing/qr/{token}")
    async def get_qr_image(token: str):
        url = token_mgr.get_share_url(token)
        qr_bytes = token_mgr.generate_qr_bytes(url)
        return Response(content=qr_bytes, media_type="image/png")

    @app.get("/download/{token}")
    async def download_guest_photo(token: str):
        """Khách tải ảnh chất lượng gốc từ mạng LAN."""
        share_obj = token_mgr.get_token(token)
        if not share_obj:
            raise HTTPException(status_code=403, detail="Đường dẫn không hợp lệ hoặc đã hết hạn.")
        share_obj.download_count += 1
        return FileResponse(
            share_obj.file_path,
            filename=f"VietPhotoBooth_{share_obj.filename}",
            media_type="image/jpeg"
        )

    # ==========================
    # API CẤU HÌNH & XÁC THỰC
    # ==========================

    @app.post("/api/admin/verify-pin")
    async def verify_pin(pin: str = Form(...)):
        is_valid = config.verify_pin(pin)
        return {"success": is_valid}

    @app.get("/api/config")
    async def get_config():
        return config.all

    @app.post("/api/config")
    async def update_config(data: Dict[str, Any]):
        success = config.update(data)
        return {"success": success}

    # ==========================
    # API NHẬT KÝ & CHẨN ĐOÁN
    # ==========================

    @app.get("/api/diagnostics")
    async def get_diagnostics():
        disk = event_mgr.check_disk_space()
        cam = camera_mgr.get_info()
        default_printer = print_mgr.get_selected_printer()
        pr_status = WindowsPrintSpooler.get_printer_status(default_printer)
        return {
            "os": "Windows 10/11 64-bit",
            "server_time": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "disk": disk,
            "camera": cam,
            "printer": {
                "name": default_printer,
                "status": pr_status
            },
            "lan_ip": token_mgr.get_local_ip(),
            "active_event": event_mgr.current_event
        }

    @app.get("/api/logs")
    async def get_logs(tail: int = 50):
        base_dir = os.environ.get("LOCALAPPDATA", os.path.expanduser("~"))
        log_file = os.path.join(base_dir, "VietPhotoBooth", "Logs", "vietphotobooth.log")
        lines = []
        if os.path.exists(log_file):
            try:
                with open(log_file, "r", encoding="utf-8", errors="ignore") as f:
                    lines = f.readlines()[-tail:]
            except Exception:
                pass
        return {"lines": [line.strip() for line in lines]}

    return app
