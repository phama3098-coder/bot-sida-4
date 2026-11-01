# CODEX_INTEGRATION_REPORT — 1998 TEAM Photobooth

**Ngày cập nhật:** 2026-11-01  
**Repository:** `C:\Users\Admin\Documents\photobooth`  
**Trạng thái:** Agent Skills đã cài và enabled. Impeccable và REA đang chờ xử lý quyền truy cập npm/network; chưa cài các thành phần này.

## Điều kiện môi trường

| Thành phần | Kiểm chứng |
|---|---|
| Codex CLI | `codex-cli 0.165.0`. Trong sandbox báo Access Denied khi tạo alias ở `.codex\tmp\arg0-windows`; chạy ngoài sandbox thì `codex --version` thành công, không cần sửa ACL. |
| Node.js | `v24.22.2`; kiểm tra lại trong PowerShell thường trước khi chạy npx. |
| npm / npx | `11.19.1`. Lệnh `npm.cmd`/`npx.cmd` hoạt động trong PowerShell thường. |
| TEMP/TMP | Đang trỏ vào thư mục tạm sandbox; phép ghi thử/dọn file ở đó thành công. Phép ghi vào `.codex\tmp` bị sandbox từ chối dù ACL của tài khoản cho quyền Full Control. Không sửa ACL. |
| Codex MCP hiện có | `C:\Users\Admin\.codex\config.toml` có `[mcp_servers.node_repl]`. Sau khi cài Agent Skills, section này vẫn còn. Chưa đăng ký REA. |

## Sao lưu cấu hình Codex

Đã sao lưu trước khi thay marketplace/plugin:

- Nguồn: `C:\Users\Admin\.codex\config.toml`
- Bản sao mới, không ghi đè: `C:\Users\Admin\.codex\backups\config.pre-photobooth-ai-tools.20261101-003137.toml.bak`
- Kích thước: 2,972 bytes
- SHA-256 nguồn và bản sao lúc tạo khớp: `5F68A06EABA456FE249CC56520BF2329B930C072C04F0F8839593D4BD2FC5BE9`

## Agent Skills — đã hoàn tất

- Đăng ký marketplace local từ `C:\Users\Admin\Documents\photobooth\agent-skills` thành công.
- Cài `agent-skills@agent-skills` từ marketplace đó thành công.
- `codex plugin list` xác nhận **installed, enabled**, phiên bản **0.6.14**.
- Bản cài có 25 skill; đã kiểm tra đủ: `code-review-and-quality`, `test-driven-development`, `performance-optimization`, `frontend-ui-engineering`, `security-and-hardening`, `debugging-and-error-recovery`, `planning-and-task-breakdown`.
- Không cài riêng các skill trùng lặp và không xóa/sửa `.agent/skills`.

## Impeccable — chưa hoàn tất

Nguồn chính thức được đối chiếu: [Impeccable docs](https://impeccable.style/docs/) và [getting started](https://impeccable.style/tutorials/getting-started/). Tài liệu nêu lệnh `npx impeccable install` và hỗ trợ Codex.

- Lần thử trong ngữ cảnh ngoài sandbox: lỗi `node is not recognized` do PATH khác; installer chưa khởi chạy. Không dùng Administrator để tiếp tục.
- Lần thử tiếp theo trong PowerShell thường: Node/npm được nhận diện nhưng npm dừng với `ENOTFOUND` khi truy cập `https://registry.npmjs.org/impeccable`.
- Đã kiểm tra `.agents\skills\impeccable` chưa được tạo. Chưa có bằng chứng Impeccable được Codex nạp hoặc gọi bằng `$impeccable`.
- Không thấy project target mới được tạo bởi installer; không có file config/source nào được ghi bởi lần chạy thất bại.

## REA — chưa bắt đầu

Nguồn chính thức được đối chiếu: [morluto/rea](https://github.com/morluto/rea). Hướng dẫn upstream phân biệt workflow skill với MCP/CLI server; setup Codex cần tải package và đăng ký client. Chưa chạy setup vì npm trong PowerShell thường không phân giải được npm registry.

- Chưa chạy `npx rea-agents@latest setup --client codex`.
- Chưa chạy `npx -y rea-agents@latest doctor --client codex --json`.
- REA chưa được xác minh cài/enable/kết nối; chưa cài workflow skill hay MCP.
- Không cài Hopper, Ghidra, IDA hoặc cấu hình client khác.

## Các lệnh kiểm chứng thực sự đã chạy

- `codex --version` (trong sandbox có cảnh báo; ngoài sandbox thành công).
- `node --version`, `npm.cmd --version`, `npx.cmd --version`.
- `codex plugin list`, `codex plugin marketplace list`.
- Đăng ký marketplace local và cài plugin Agent Skills.
- Kiểm tra trạng thái plugin, 7 skill bắt buộc, section MCP hiện có và đích Impeccable.
- `npx.cmd impeccable install` trong PowerShell thường — thất bại trước khi installer chạy vì npm registry trả `ENOTFOUND`.

Không sửa source code Photobooth, Nikon MAID Type0026, version hoặc installer. Không ghi đè MCP hiện có. Không sửa ACL. Không khẳng định Impeccable/REA đã cài.

## Cần xác nhận để tiếp tục Impeccable và REA

Bạn đã cho phép tiếp tục npx nếu cần và yêu cầu hỏi nếu cần Administrator, chỉnh ACL hệ thống hoặc có rủi ro bảo mật. Hiện PowerShell thường bị lỗi DNS tới npm registry; môi trường ngoài sandbox có thể truy cập mạng nhưng lần gọi npx trước chạy với PATH thiếu `node`, và tiêu đề terminal cho biết ngữ cảnh có thể là Administrator.

Để tiếp tục mà không vượt giới hạn đã nêu, cần một trong hai điều kiện:

1. Khôi phục DNS/proxy cho `registry.npmjs.org` trong PowerShell thường, sau đó chạy lại các installer không nâng quyền; hoặc
2. Xác nhận rõ cho phép dùng ngữ cảnh thực thi có thể là Administrator, đồng thời chạy `npx` với PATH Node đầy đủ. Tôi sẽ không chỉnh ACL hệ thống.

Sau khi điều kiện có sẵn, sẽ kiểm tra nguồn package, sao lưu/soát các file đích trước thay đổi, cài Impeccable với provider Codex + scope project, xem trước kế hoạch REA trước khi xác nhận, rồi kiểm tra plugin/skill/MCP bằng tác vụ chỉ đọc. Cần session Codex mới để kiểm chứng discovery; chưa khởi động lại phiên trong bước này.
