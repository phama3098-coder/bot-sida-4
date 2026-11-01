/**
 * 1998 TEAM PHOTOBOOTH — HYBRID INTERACTIVE PROTOTYPE ENGINE (ROUND 2.1 REFINED)
 * Bộ điều khiển tương tác phản ứng (Interactive Application Logic)
 * Tích hợp: Hybrid Architecture + 4-Slot Retake với 4 Ảnh Riêng Biệt + Pose Guidance + Concept C Telemetry
 * 
 * LƯU Ý BẢO TOÀN CAMERA & THIẾT BỊ:
 * Mọi số liệu và trạng thái trong prototype này là [DEMO / SIMULATED], không can thiệp
 * vào backend Nikon MAID3, driver Windows WPD hay ứng dụng chính v1.6.6 Build 166.
 */

document.addEventListener("DOMContentLoaded", () => {
  // Khởi tạo âm thanh giả lập từ các file WAV chính thức của dự án
  const audioTick = new Audio("assets/countdown_tick.wav");
  const audioVoice = new Audio("assets/countdown_voice_vi.wav");
  const audioShutter = new Audio("assets/shutter_click.wav");

  function playSound(audio) {
    try {
      audio.currentTime = 0;
      audio.play().catch(() => {});
    } catch (e) {}
  }

  // --------------------------------------------------------------------------
  // CONCEPT C MULTI-CHANNEL DEVICE TELEMETRY RENDERER
  // (Không dựa vào màu sắc đơn thuần làm tín hiệu duy nhất: Icon + Label + Value + Border)
  // --------------------------------------------------------------------------

  function renderDeviceStatusPill(devType) {
    const dev = MOCK_DATA.devices[devType];
    let badgeClass = "connected";
    let icon = "✓";
    let label = dev.state_label || "CONNECTED";

    if (dev.state === "CONNECTING") {
      badgeClass = "busy";
      icon = "⏳";
      label = "CONNECTING (PTP)";
    } else if (dev.state === "BUSY") {
      badgeClass = "busy";
      icon = "⚡";
      label = "BUSY / SD BUFFER";
    } else if (dev.state === "WARNING" || dev.state === "OUT_OF_PAPER") {
      badgeClass = "warning";
      icon = "⚠️";
      label = dev.state === "OUT_OF_PAPER" ? "OUT OF PAPER" : "WARNING / HEAT";
    } else if (dev.state === "ERROR" || dev.state === "SPOOLER_ERROR") {
      badgeClass = "error";
      icon = "✕";
      label = dev.state === "SPOOLER_ERROR" ? "SPOOLER ERROR" : "ERROR / LOCKED";
    } else if (dev.state === "DISCONNECTED") {
      badgeClass = "disconnected";
      icon = "⏻";
      label = "DISCONNECTED";
    }

    let title = "";
    let val = "";
    if (devType === "camera") {
      title = "MÁY ẢNH (NIKON D780)";
      val = `${dev.model} (${dev.battery}% Pin [MOCK])`;
    } else if (devType === "printer") {
      title = "MÁY IN NHIỆT (DNP)";
      val = `${dev.model} (${store.getState().paperRemaining}/700 Giấy [SIMULATED])`;
    } else if (devType === "network") {
      title = "MẠNG NỘI BỘ (OFFLINE)";
      val = `${dev.server_ip}:${dev.port} (${dev.connected_clients} Khách [SIMULATED])`;
    }

    return `
      <div class="led-status-pill status-pill-${badgeClass}">
        <div class="led-info">
          <span class="led-name">${title}</span>
          <span class="led-val">${val}</span>
        </div>
        <div class="status-badge ${badgeClass}">
          <span class="status-icon">${icon}</span>
          <span>${label}</span>
        </div>
      </div>
    `;
  }

  // --------------------------------------------------------------------------
  // RENDER OPERATOR VIEWS (CONCEPT A — PREMIUM STUDIO)
  // --------------------------------------------------------------------------

  function renderDashboard() {
    const s = store.getState();
    const evt = s.currentEvent;
    const tpl = s.currentTemplate;
    const dev = MOCK_DATA.devices;

    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Bảng Điều Khiển Vận Hành (Dashboard)</h1>
          <p class="page-subtitle">Buồng lái tác nghiệp trung tâm 1998 TEAM — Giám sát sự kiện, thiết bị và hàng đợi</p>
        </div>
        <button class="mode-toggle-btn" onclick="startKioskMode()">
          🚀 BẮT ĐẦU PHOTOBOOTH (F11)
        </button>
      </div>

      <!-- Banner Thông Báo Minh Bạch Dữ Liệu Demo / Simulation -->
      <div class="simulated-banner">
        <span>⚠️</span>
        <div><b>BUỒNG LÁI VẬN HÀNH 1998 TEAM:</b> Dữ liệu phiên, bản in và các thông số telemetry phần cứng được biểu diễn ở chế độ <b>[DEMO / SIMULATED]</b> nhằm xác thực trải nghiệm UI/UX. Camera engine thực tế tuân thủ driver Windows WPD và Nikon MAID3 SDK.</div>
      </div>

      <!-- 4 Stat Cards với nhãn DEMO / SIMULATED minh bạch -->
      <div class="stats-grid-4">
        <div class="stat-card">
          <div class="stat-icon-wrap" style="color: #3B82F6;">📅</div>
          <div class="stat-content">
            <div class="stat-label">SỰ KIỆN HOẠT ĐỘNG</div>
            <div class="stat-value" style="font-size: 16px;">${evt.name}</div>
            <div class="stat-meta">📍 ${evt.location}</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrap" style="color: #10B981;">📸</div>
          <div class="stat-content">
            <div class="stat-label">PHIÊN ĐÃ CHỤP <span class="simulated-pill">DEMO</span></div>
            <div class="stat-value">${s.sessionCount}</div>
            <div class="stat-meta">Hôm nay: +${s.sessionCount} lượt khách [DEMO]</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrap" style="color: #F59E0B;">🖨️</div>
          <div class="stat-content">
            <div class="stat-label">BẢN IN THÀNH PHẨM <span class="simulated-pill">DEMO</span></div>
            <div class="stat-value">${s.printCount}</div>
            <div class="stat-meta">100% bản in hoàn tất [DEMO]</div>
          </div>
        </div>

        <div class="stat-card">
          <div class="stat-icon-wrap" style="color: #EC4899;">📜</div>
          <div class="stat-content">
            <div class="stat-label">GIẤY IN CÒN LẠI (DNP) <span class="simulated-pill">SIMULATED</span></div>
            <div class="stat-value">${s.paperRemaining} <span style="font-size: 13px; font-weight: 400; color: var(--text-muted);">/ 700</span></div>
            <div class="progress-gauge">
              <div class="progress-gauge-fill" style="width: ${(s.paperRemaining/700)*100}%;"></div>
            </div>
            <div class="stat-meta">${Math.round((s.paperRemaining/700)*100)}% dung lượng cuộn giấy [SIMULATED]</div>
          </div>
        </div>
      </div>

      <!-- Cockpit Split 2 Panels: Trọng tâm Live View & Thiết Bị -->
      <div class="cockpit-split-2">
        <!-- Cột trái: Trạng thái phần cứng Concept C & Kiểm tra Live View -->
        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">⚡ Trạng Thái Phần Cứng (Concept C Multi-Channel)</div>
            <button class="btn-theme-choice" onclick="cycleDeviceState()" title="Bấm để thử nghiệm các trạng thái Warning/Busy/Error">
              🔄 Thử Trạng Thái
            </button>
          </div>

          <div class="hardware-status-row">
            ${renderDeviceStatusPill("camera")}
            ${renderDeviceStatusPill("printer")}
            ${renderDeviceStatusPill("network")}
          </div>

          <!-- Live View preview trung tâm -->
          <div class="liveview-frame-container" style="max-height: 270px; margin-bottom: 16px;">
            <img src="assets/slot_1_pose_wave.jpg" class="liveview-camera-feed" alt="Live View">
            <div class="liveview-face-box">
              <span class="face-tag">FACE/EYE AF: [SIMULATED AF TRACKING]</span>
            </div>
            <div class="liveview-hud">
              <span>● LIVE VIEW FEED: SIMULATED (DEMO MODE)</span>
              <span>${dev.camera.aperture} | ${dev.camera.shutter_speed} | ISO ${dev.camera.iso}</span>
            </div>
          </div>

          <div class="studio-action-toolbar">
            <button class="btn-studio-action" onclick="simulateTestCapture()">
              📸 Test Chụp Thử
            </button>
            <button class="btn-studio-action" onclick="simulateTestPrint()">
              🖨️ Test In Thử
            </button>
            <button class="btn-studio-action primary" onclick="store.setView('capture')">
              🔍 Mở Toàn Bộ Studio
            </button>
          </div>
        </div>

        <!-- Cột phải: Template đang kích hoạt & Thao tác nhanh -->
        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">🎨 Khung Ảnh Đang Áp Dụng (Template)</div>
            <button class="btn-theme-choice" onclick="store.setView('templates')">Thay Đổi Khung</button>
          </div>

          <div style="display: flex; gap: 20px; align-items: center; margin-bottom: 16px;">
            <div style="width: 130px; aspect-ratio: 2/3; border-radius: 8px; overflow: hidden; border: 2px solid var(--border-color); flex-shrink: 0;">
              <img src="${tpl.thumbnail}" style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            <div>
              <h3 style="font-size: 16px; margin-bottom: 6px;">${tpl.name}</h3>
              <p style="font-size: 12px; color: var(--text-muted); margin-bottom: 8px;">${tpl.description}</p>
              <div style="display: flex; flex-wrap: wrap; gap: 6px;">
                <span class="demo-brand-tag">${tpl.category_name}</span>
                <span class="demo-brand-tag" style="background: rgba(225, 29, 72, 0.15); color: #E11D48; border-color: rgba(225, 29, 72, 0.3); font-weight: 800;">${tpl.slots_count} Ô ẢNH RIÊNG BIỆT</span>
                <span class="demo-brand-tag">${tpl.dimensions_mm}</span>
              </div>
            </div>
          </div>

          <div style="background: var(--bg-card-subtle); padding: 14px; border-radius: var(--radius-btn); margin-bottom: 16px;">
            <div style="font-size: 12px; font-weight: 700; margin-bottom: 4px;">GHI CHÚ SỰ KIỆN:</div>
            <div style="font-size: 12px; color: var(--text-secondary);">${evt.notes}</div>
          </div>

          <button class="btn-start-kiosk-main" onclick="startKioskMode()">
            ⚡ CHUYỂN SANG CHẾ ĐỘ KHÁCH CHỤP (KIOSK)
          </button>
        </div>
      </div>
    `;
  }

  function renderCaptureStudio() {
    const s = store.getState();
    const tpl = s.currentTemplate;
    const dev = MOCK_DATA.devices;

    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Capture Studio — Buồng Chụp Kỹ Thuật</h1>
          <p class="page-subtitle">Giám sát Live View thời gian thực [SIMULATED MOCK] • Quy chuẩn Camera Nikon D780 & Face/Eye AF</p>
        </div>
        <div style="display: flex; gap: 10px;">
          <button class="btn-studio-action" onclick="toggleMirror()">🪞 Đổi Lật Gương</button>
          <button class="btn-studio-action" onclick="simulateTestCapture()">📸 Chụp Thử</button>
          <button class="mode-toggle-btn" onclick="startKioskMode()">Bắt Đầu Kiosk</button>
        </div>
      </div>

      <!-- Toolbar Thử Chuyển Đổi Trạng Thái Camera Toàn Diện -->
      <div class="state-switcher-toolbar">
        <span style="font-size: 12px; font-weight: 800; color: var(--text-muted); margin-right: 4px;">⚡ THỬ TRẠNG THÁI CAMERA:</span>
        <button class="state-switcher-btn ${dev.camera.state === 'CONNECTED' ? 'active' : ''}" onclick="store.setCameraState('CONNECTED')">✓ Connected (Sẵn Sàng)</button>
        <button class="state-switcher-btn ${dev.camera.state === 'CONNECTING' ? 'active' : ''}" onclick="store.setCameraState('CONNECTING')">⏳ Connecting (Bắt Tay PTP)</button>
        <button class="state-switcher-btn ${dev.camera.state === 'BUSY' ? 'active' : ''}" onclick="store.setCameraState('BUSY')">⚡ Busy (Đang Xả Buffer)</button>
        <button class="state-switcher-btn ${dev.camera.state === 'WARNING' ? 'active' : ''}" onclick="store.setCameraState('WARNING')">⚠️ Warning (Nhiệt/Pin)</button>
        <button class="state-switcher-btn ${dev.camera.state === 'ERROR' ? 'active' : ''}" onclick="store.setCameraState('ERROR')">✕ Error (Lỗi Trập/Thẻ)</button>
        <button class="state-switcher-btn ${dev.camera.state === 'DISCONNECTED' ? 'active' : ''}" onclick="store.setCameraState('DISCONNECTED')">✕ Disconnected (Mất Cáp)</button>
      </div>

      <div class="cockpit-split-2" style="grid-template-columns: 2fr 1fr;">
        <!-- Live View Lớn Trung Tâm -->
        <div class="cockpit-panel" style="padding: 16px;">
          <div class="liveview-frame-container" style="height: 540px;">
            <img src="assets/slot_1_pose_wave.jpg" class="liveview-camera-feed" id="studio-feed" alt="Studio Feed">
            <div class="liveview-overlay-grid"></div>
            <div class="liveview-face-box">
              <span class="face-tag">FACE/EYE AF: [SIMULATED AF TRACKING - BENCH TEST REQUIRED]</span>
            </div>
            <div class="liveview-hud">
              <div><b>NIKON D780</b> | USB 3.0 Tethered [SIMULATED] | Pin: 92% [MOCK]</div>
              <div>Khẩu độ: f/2.8 [MOCK] | Trập: 1/160s [MOCK] | ISO: 400 [MOCK] | AF-S</div>
            </div>
            <div class="shutter-flash-overlay" id="studio-flash"></div>
          </div>

          <div class="studio-action-toolbar" style="margin-top: 14px;">
            <button class="btn-studio-action" onclick="simulateFlashTest()">💡 Test Đèn Flash</button>
            <button class="btn-studio-action" onclick="simulateVoiceTest()">🔊 Test Giọng Nói Đếm Ngược</button>
            <button class="btn-studio-action" onclick="store.showToast('Nikon D780: Đã tái lấy nét (AF Lock OK [MOCK])', 'success')">🎯 Tái Lấy Nét (AF)</button>
          </div>
        </div>

        <!-- Cột Phải: Tiến trình 4 Slots với 4 tư thế rõ ràng -->
        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">Tiến Trình 4 Ô Ảnh (Slots)</div>
            <span class="demo-brand-tag">4 Tư Thế Riêng Biệt</span>
          </div>

          <div style="margin-bottom: 16px;">
            <div style="font-size: 13px; font-weight: 700; margin-bottom: 4px;">${tpl.name}</div>
            <div style="font-size: 12px; color: var(--text-muted);">${tpl.dimensions_mm} • Hỗ trợ Slot-based Retake độc lập</div>
          </div>

          <div style="display: flex; flex-direction: column; gap: 8px; margin-bottom: 20px;">
            ${MOCK_DATA.slot_poses.map((p, i) => `
              <div style="display: flex; align-items: center; justify-content: space-between; background: var(--bg-card-subtle); padding: 10px 12px; border-radius: var(--radius-btn); border: 1px solid var(--border-subtle);">
                <div>
                  <span style="font-size: 12px; font-weight: 700; color: ${p.tone_color};">Ô #${i + 1}:</span>
                  <span style="font-size: 12px; font-weight: 600;"> ${p.pose_name}</span>
                </div>
                <span style="font-size: 11px; color: #10B981; font-weight: 700;">✓ Sẵn sàng</span>
              </div>
            `).join('')}
          </div>

          <div style="background: var(--bg-card-subtle); border-radius: var(--radius-btn); padding: 14px; margin-bottom: 20px;">
            <div style="font-size: 11px; font-weight: 700; color: var(--text-muted); margin-bottom: 6px;">BẢO TOÀN CAMERA ENGINE (WINDOWS WPD NATIVE):</div>
            <div style="font-size: 12px; line-height: 1.6; color: var(--text-secondary);">
              • Driver: <b>Windows WPD Native (Bảo toàn)</b><br>
              • Session MAID: <b>Không bị ngắt khi chuyển tab</b><br>
              • Thẻ nhớ còn trống: <b>58.4 GB [SIMULATED]</b><br>
              • Thông số điều khiển: <b>[MOCK / SIMULATED PARAMETERS]</b>
            </div>
          </div>

          <button class="btn-start-kiosk-main" onclick="startKioskMode()">
            BẮT ĐẦU PHIÊN CHỤP
          </button>
        </div>
      </div>
    `;
  }

  function renderEvents() {
    const s = store.getState();
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Quản Lý Sự Kiện (Events)</h1>
          <p class="page-subtitle">Mỗi sự kiện là một phân vùng độc lập lưu trữ ảnh gốc, bản in và thống kê</p>
        </div>
        <button class="btn-studio-action primary" onclick="store.showToast('Mở hộp thoại tạo sự kiện mới', 'info')">
          ➕ Tạo Sự Kiện Mới
        </button>
      </div>

      <div style="display: flex; flex-direction: column; gap: 16px;">
        ${MOCK_DATA.events.map(e => `
          <div class="stat-card" style="justify-content: space-between; border-color: ${e.active ? 'var(--border-focus)' : 'var(--border-subtle)'};">
            <div style="display: flex; align-items: center; gap: 16px;">
              <div class="stat-icon-wrap" style="color: ${e.active ? 'var(--brand-primary)' : 'var(--text-muted)'};">
                ${e.active ? '⭐' : '📅'}
              </div>
              <div>
                <div style="display: flex; align-items: center; gap: 10px; margin-bottom: 4px;">
                  <span style="font-size: 17px; font-weight: 800; color: var(--text-primary);">${e.name}</span>
                  ${e.active ? '<span class="status-badge connected">✓ ĐANG HOẠT ĐỘNG</span>' : ''}
                </div>
                <div style="font-size: 12px; color: var(--text-secondary);">
                  📍 ${e.location} &nbsp;|&nbsp; 🗓️ ${e.date} &nbsp;|&nbsp; 📁 ${e.storage_folder}
                </div>
                <div style="font-size: 12px; color: var(--text-muted); margin-top: 4px;">
                  📝 Ghi chú: ${e.notes}
                </div>
              </div>
            </div>

            <div style="display: flex; align-items: center; gap: 24px;">
              <div style="text-align: right;">
                <div style="font-size: 18px; font-weight: 800;">${e.total_sessions} phiên</div>
                <div style="font-size: 11px; color: var(--text-muted);">${e.total_prints} bản in</div>
              </div>

              <div>
                ${e.active ? 
                  `<button class="btn-theme-choice" onclick="store.setView('gallery')">Xem Thư Viện Ảnh</button>` :
                  `<button class="btn-theme-choice active" onclick="store.setEvent('${e.id}')">Kích Hoạt</button>`
                }
              </div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  function renderTemplates() {
    const s = store.getState();
    const currentCat = s.templateCategory;
    const filtered = currentCat === "all" ? 
      MOCK_DATA.templates : 
      MOCK_DATA.templates.filter(t => t.category === currentCat);

    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Thư Viện Khung Ảnh (Templates)</h1>
          <p class="page-subtitle">Chọn mẫu khung phù hợp với phong cách sự kiện (1x4, 2x6, 4x6, 2x2)</p>
        </div>
        <button class="btn-studio-action" onclick="store.setView('designer')">
          🎨 Mở Frame Designer
        </button>
      </div>

      <!-- Categories Filter Chips -->
      <div class="category-chips-row">
        ${MOCK_DATA.categories.map(c => `
          <button class="chip-btn ${c.id === currentCat ? 'active' : ''}" onclick="setTemplateFilter('${c.id}')">
            ${c.icon} ${c.name}
          </button>
        `).join('')}
      </div>

      <!-- Grid Template Cards -->
      <div class="templates-grid">
        ${filtered.map(t => `
          <div class="template-card ${t.id === s.currentTemplate.id ? 'active' : ''}" onclick="store.setTemplate('${t.id}')">
            ${t.id === s.currentTemplate.id ? '<span class="template-active-badge">✓ ĐANG DÙNG</span>' : ''}
            <div class="template-thumb-wrap">
              <img src="${t.thumbnail}" alt="${t.name}">
            </div>
            <div class="template-meta">
              <div class="template-title">${t.name}</div>
              <div class="template-desc">${t.slots_count} ô ảnh • ${t.dimensions_mm}</div>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  function renderGallery() {
    const s = store.getState();
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Thư Viện Ảnh Sự Kiện (Gallery)</h1>
          <p class="page-subtitle">Ảnh thành phẩm và ảnh gốc của sự kiện: <b>${s.currentEvent.name}</b></p>
        </div>
        <div style="display: flex; gap: 10px;">
          <button class="btn-studio-action" onclick="store.showToast('Đã làm mới thư viện ảnh', 'success')">🔄 Làm Mới</button>
          <button class="btn-studio-action" onclick="store.showToast('Mở thư mục lưu trữ trên máy tính', 'info')">📁 Mở Thư Mục Lưu</button>
        </div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(260px, 1fr)); gap: 20px;">
        ${MOCK_DATA.gallery.map(p => `
          <div class="cockpit-panel" style="padding: 12px;">
            <div style="width: 100%; aspect-ratio: 4/3; border-radius: 8px; overflow: hidden; margin-bottom: 10px; background: #000;">
              <img src="${p.composite_url}" style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
              <span style="font-size: 13px; font-weight: 700;">${p.session_id}</span>
              <span class="status-badge connected">ĐÃ IN (${p.copies})</span>
            </div>
            <div style="font-size: 11px; color: var(--text-muted); margin-bottom: 4px;">
              ⏱️ ${p.timestamp} &nbsp;|&nbsp; 👤 ${p.client_name}
            </div>
            <div style="font-size: 11px; color: #10B981; font-weight: 600; margin-bottom: 12px;">
              🔄 ${p.retake_history}
            </div>
            <div style="display: flex; gap: 8px;">
              <button class="btn-studio-action" style="flex: 1; padding: 6px;" onclick="reprintPhoto('${p.session_id}')">
                🖨️ In Lại
              </button>
              <button class="btn-studio-action" style="flex: 1; padding: 6px;" onclick="showQrForPhoto('${p.session_id}')">
                📱 Xem QR
              </button>
            </div>
          </div>
        `).join('')}
      </div>
    `;
  }

  function renderPrinting() {
    const s = store.getState();
    const prn = MOCK_DATA.devices.printer;
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Quản Lý Máy In Nhiệt (Printing Center)</h1>
          <p class="page-subtitle">Giám sát máy in nhiệt DNP DS-RX1HS, lượng giấy, ruy-băng và hàng đợi in [SIMULATED METRICS]</p>
        </div>
        <button class="btn-studio-action" onclick="simulateTestPrint()">
          🖨️ In Trang Kiểm Tra
        </button>
      </div>

      <!-- Toolbar Thử Chuyển Đổi Trạng Thái Máy In -->
      <div class="state-switcher-toolbar">
        <span style="font-size: 12px; font-weight: 800; color: var(--text-muted); margin-right: 4px;">⚡ THỬ TRẠNG THÁI MÁY IN:</span>
        <button class="state-switcher-btn ${prn.state === 'CONNECTED' ? 'active' : ''}" onclick="store.setPrinterState('CONNECTED')">✓ Ready (Sẵn Sàng In)</button>
        <button class="state-switcher-btn ${prn.state === 'OUT_OF_PAPER' ? 'active' : ''}" onclick="store.setPrinterState('OUT_OF_PAPER')">⚠️ Out of Paper (Hết Cuộn Giấy)</button>
        <button class="state-switcher-btn ${prn.state === 'SPOOLER_ERROR' ? 'active' : ''}" onclick="store.setPrinterState('SPOOLER_ERROR')">✕ Spooler Error (Lỗi Hàng Đợi)</button>
        <button class="state-switcher-btn ${prn.state === 'DISCONNECTED' ? 'active' : ''}" onclick="store.setPrinterState('DISCONNECTED')">✕ Disconnected (Mất Cáp USB)</button>
      </div>

      <div class="cockpit-split-2">
        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">Trạng Thái Máy In DNP DS-RX1HS</div>
            <span class="status-badge ${prn.state === 'CONNECTED' ? 'connected' : (prn.state === 'OUT_OF_PAPER' ? 'warning' : 'error')}">
              ${prn.state_icon} ${prn.state_label}
            </span>
          </div>

          <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin-bottom: 20px;">
            <div style="background: var(--bg-card-subtle); padding: 16px; border-radius: var(--radius-btn);">
              <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">CUỘN GIẤY CÒN LẠI <span class="simulated-pill">SIMULATED</span></div>
              <div style="font-size: 26px; font-weight: 800; color: var(--text-primary);">${s.paperRemaining} <span style="font-size: 13px; font-weight: 400;">/ 700 bản</span></div>
              <div class="progress-gauge" style="margin-top: 8px;">
                <div class="progress-gauge-fill" style="width: ${(s.paperRemaining/700)*100}%;"></div>
              </div>
            </div>

            <div style="background: var(--bg-card-subtle); padding: 16px; border-radius: var(--radius-btn);">
              <div style="font-size: 12px; color: var(--text-muted); margin-bottom: 4px;">RUY-BĂNG MỰC CÒN LẠI <span class="simulated-pill">SIMULATED</span></div>
              <div style="font-size: 26px; font-weight: 800; color: var(--text-primary);">${prn.ribbon_remaining_pct}%</div>
              <div class="progress-gauge" style="margin-top: 8px;">
                <div class="progress-gauge-fill" style="width: ${prn.ribbon_remaining_pct}%; background: #3B82F6;"></div>
              </div>
            </div>
          </div>

          <div style="background: var(--bg-card-subtle); padding: 16px; border-radius: var(--radius-btn); line-height: 1.8; font-size: 13px; margin-bottom: 16px;">
            • Kết nối: <b>${prn.connection}</b><br>
            • Khổ giấy nạp: <b>${prn.paper_name}</b><br>
            • Nhiệt độ đầu in: <b>${prn.head_temp}</b><br>
            • Cấu hình Pacing: <b>${prn.pacing_delay}</b> (Bảo vệ giãn nhiệt)<br>
            • Vùng an toàn viền: <b>${prn.safety_margin}</b> (Fit 98% chống cắt lẹm)
          </div>

          <div style="display: flex; gap: 10px;">
            <button class="btn-studio-action" onclick="store.showToast('Đã cắt giấy thử (Test Cut OK [SIMULATED])', 'success')">✂️ Cắt Giấy Thử</button>
            <button class="btn-studio-action" onclick="store.showToast('Đã kích hoạt làm mát đầu in', 'info')">❄️ Làm Mát Đầu In</button>
          </div>
        </div>

        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">Hàng Đợi In Thời Gian Thực (Spooler)</div>
            <span style="font-size: 12px; color: var(--text-muted);">0 lệnh chờ [MOCK]</span>
          </div>

          <div style="display: flex; flex-direction: column; gap: 10px;">
            ${MOCK_DATA.print_queue.map(q => `
              <div style="display: flex; justify-content: space-between; align-items: center; background: var(--bg-card-subtle); padding: 12px 14px; border-radius: var(--radius-btn);">
                <div>
                  <div style="font-size: 13px; font-weight: 700;">Lệnh In #${q.id} — Phiên ${q.session}</div>
                  <div style="font-size: 11px; color: var(--text-muted);">Thời gian: ${q.time} &nbsp;|&nbsp; Số bản: ${q.copies} dải</div>
                </div>
                <span class="status-badge connected">✓ HOÀN TẤT</span>
              </div>
            `).join('')}
          </div>
        </div>
      </div>
    `;
  }

  function renderQRSharing() {
    const net = MOCK_DATA.devices.network;
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Chia Sẻ Mã QR Nội Bộ (Local Offline QR)</h1>
          <p class="page-subtitle">Khách quét mã tải ảnh trực tiếp qua sóng WiFi Kiosk, bảo mật 100%, không cần Internet</p>
        </div>
        <button class="btn-studio-action primary" onclick="store.showToast('Đã khởi động lại mạng WiFi Hotspot nội bộ', 'success')">
          🔄 Khởi Động Lại Hotspot
        </button>
      </div>

      <div class="cockpit-split-2">
        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">Mạng WiFi Cục Bộ Phát Sóng</div>
            <span class="status-badge connected">✓ ĐANG PHÁT SÓNG</span>
          </div>

          <div style="background: var(--bg-card-subtle); padding: 18px; border-radius: var(--radius-btn); line-height: 1.8; font-size: 13px; margin-bottom: 20px;">
            • Tên WiFi (SSID): <b style="color: var(--text-accent);">${net.hotspot_name}</b><br>
            • Mật khẩu: <b>1998photobooth</b><br>
            • Địa chỉ máy chủ (IP): <b>${net.server_ip}:${net.port}</b><br>
            • Thiết bị di động đang kết nối: <b>${net.connected_clients} điện thoại [SIMULATED]</b><br>
            • Tốc độ truyền tải: <b>Tức thời (Băng thông mạng nội bộ 5GHz)</b>
          </div>

          <div style="text-align: center;">
            <div style="font-size: 13px; font-weight: 700; margin-bottom: 12px;">MÃ QR MẪU DÀNH CHO KHÁCH:</div>
            <div style="display: inline-block; background: #FFF; padding: 12px; border-radius: 8px;">
              <img src="assets/slot_1_pose_wave.jpg" style="width: 160px; height: 120px; object-fit: cover; border-radius: 4px;">
            </div>
          </div>
        </div>

        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">Xem Trước Giao Diện Điện Thoại Của Khách</div>
            <span class="demo-brand-tag">Giao Diện Khách (Mobile Web)</span>
          </div>

          <div style="width: 240px; margin: 0 auto; border: 4px solid var(--border-color); border-radius: 28px; padding: 12px; background: var(--bg-app); box-shadow: var(--shadow-floating);">
            <div style="width: 60px; height: 4px; background: var(--border-subtle); border-radius: 9999px; margin: 0 auto 12px auto;"></div>
            <div style="text-align: center; margin-bottom: 10px;">
              <div style="font-size: 12px; font-weight: 800;">1998 TEAM</div>
              <div style="font-size: 9px; color: var(--text-muted);">Tải ảnh kỷ niệm của bạn</div>
            </div>
            <div style="width: 100%; aspect-ratio: 4/3; border-radius: 6px; overflow: hidden; margin-bottom: 10px;">
              <img src="assets/slot_2_pose_retaken_new.jpg" style="width: 100%; height: 100%; object-fit: cover;">
            </div>
            <button class="btn-start-kiosk-main" style="padding: 6px; font-size: 11px;">
              💾 Tải Ảnh Gốc (10MB)
            </button>
          </div>
        </div>
      </div>
    `;
  }

  function renderDevices() {
    const dev = MOCK_DATA.devices;
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Giám Sát & Chẩn Đoán Thiết Bị (Devices)</h1>
          <p class="page-subtitle">Kiểm tra thông số kỹ thuật chi tiết của Máy ảnh, Máy in và Mạng ngoại vi [SIMULATED TELEMETRY]</p>
        </div>
        <button class="btn-studio-action primary" onclick="runSelfTest()">
          🩺 Chẩn Đoán Toàn Bộ Hệ Thống
        </button>
      </div>

      <!-- Banner Minh Bạch Về Telemetry Phần Cứng -->
      <div class="simulated-banner">
        <span>⚠️</span>
        <div><b>BÁO CÁO THỬ NGHIỆM:</b> Toàn bộ các thông số telemetry dưới đây là mô phỏng <b>[SIMULATED TELEMETRY]</b> để kiểm thử UI đa kênh Concept C. Ứng dụng thực tế chạy qua driver Windows WPD và Nikon MAID3 SDK yêu cầu kiểm thử phần cứng độc lập (Bench Test).</div>
      </div>

      <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 20px;">
        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">📷 Nikon D780 DSLR</div>
            <span class="status-badge connected">✓ CONNECTED</span>
          </div>
          <div style="font-size: 13px; line-height: 1.8; color: var(--text-secondary);">
            • Backend: <b>${dev.camera.backend}</b><br>
            • Mức pin: <b>${dev.camera.battery}% [MOCK]</b><br>
            • Số shot trập đã chụp: <b>${dev.camera.shutter_count.toLocaleString()} [MOCK]</b><br>
            • Bộ nhớ thẻ SD còn: <b>${(dev.camera.storage_free_mb/1024).toFixed(1)} GB [MOCK]</b><br>
            • Live View: <b>${dev.camera.live_view_fps} FPS [SIMULATED]</b><br>
            • Lấy nét: <b>${dev.camera.focus_mode}</b>
          </div>
        </div>

        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">🖨️ DNP DS-RX1HS</div>
            <span class="status-badge connected">✓ READY</span>
          </div>
          <div style="font-size: 13px; line-height: 1.8; color: var(--text-secondary);">
            • Giấy in còn: <b>${dev.printer.paper_remaining} bản [SIMULATED]</b><br>
            • Ruy-băng mực: <b>${dev.printer.ribbon_remaining_pct}% [SIMULATED]</b><br>
            • Tình trạng nắp: <b>Đã đóng chặt</b><br>
            • Nhiệt độ đầu in: <b>${dev.printer.head_temp}</b><br>
            • Độ an toàn viền: <b>${dev.printer.safety_margin}</b><br>
            • Thời gian in trung bình: <b>12.4 giây / bản</b>
          </div>
        </div>

        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">📡 WiFi Hotspot LAN</div>
            <span class="status-badge connected">✓ BROADCASTING</span>
          </div>
          <div style="font-size: 13px; line-height: 1.8; color: var(--text-secondary);">
            • Băng tần: <b>5.0 GHz (Ưu tiên tốc độ)</b><br>
            • Địa chỉ Gateway: <b>${dev.network.server_ip}</b><br>
            • Cổng HTTP: <b>${dev.network.port}</b><br>
            • Trạng thái phát: <b>Không cần Internet</b><br>
            • Tốc độ truyền file: <b>~25 MB/s</b>
          </div>
        </div>
      </div>
    `;
  }

  function renderSettings() {
    const s = store.getState();
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Cài Đặt Hệ Thống (Settings)</h1>
          <p class="page-subtitle">Thiết lập các tham số âm thanh, in ấn và mã bảo mật quản trị viên</p>
        </div>
        <button class="btn-studio-action primary" onclick="store.showToast('Đã lưu cấu hình hệ thống', 'success')">
          💾 Lưu Thiết Lập
        </button>
      </div>

      <div class="cockpit-split-2">
        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">Âm Thanh Studio (Studio Audio)</div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 16px;">
            <div>
              <label style="font-size: 13px; font-weight: 700; display: block; margin-bottom: 6px;">Âm Lượng Loa Kiosk (100%):</label>
              <input type="range" min="0" max="100" value="85" style="width: 100%;">
            </div>
            <div>
              <label style="font-size: 13px; font-weight: 700; display: block; margin-bottom: 6px;">Giọng Đọc Đếm Ngược:</label>
              <select style="width: 100%; padding: 10px; background: var(--bg-card-subtle); color: var(--text-primary); border: 1px solid var(--border-subtle); border-radius: var(--radius-btn);">
                <option selected>Tiếng Việt (Nữ miền Nam thân thiện)</option>
                <option>Tiếng Việt (Nữ miền Bắc truyền cảm)</option>
                <option>Tiếng Anh (International English)</option>
                <option>Chỉ phát tiếng bíp cơ khí (Beep Only)</option>
              </select>
            </div>
          </div>
        </div>

        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">Bảo Mật Kiosk & Đổi Mã PIN Quản Trị</div>
          </div>
          <div style="display: flex; flex-direction: column; gap: 16px;">
            <div>
              <label style="font-size: 13px; font-weight: 700; display: block; margin-bottom: 6px;">Mã PIN Thoát Kiosk Hiện Tại:</label>
              <input type="password" id="admin-pin-input" value="${s.adminPin}" style="width: 100%; padding: 10px; background: var(--bg-card-subtle); color: var(--text-primary); border: 1px solid var(--border-subtle); border-radius: var(--radius-btn);">
              <span style="font-size: 11px; color: var(--text-muted); margin-top: 4px; display: block;">Mã PIN mặc định: <b>1998</b>. Bạn có thể thay đổi và lưu tại đây.</span>
            </div>
            <div>
              <button class="btn-studio-action" onclick="updateAdminPin()">Cập Nhật Mã PIN Mới</button>
            </div>
          </div>
        </div>
      </div>
    `;
  }

  function renderDesigner() {
    return `
      <div class="page-header">
        <div>
          <h1 class="page-title">Trình Thiết Kế Khung Ảnh (Frame Designer)</h1>
          <p class="page-subtitle">Công cụ quản trị độc lập để căn chỉnh tọa độ 4 ô ảnh, chèn logo và lớp phủ trang trí</p>
        </div>
        <div style="display: flex; gap: 10px;">
          <button class="btn-studio-action" onclick="store.setView('templates')">Thoát Về Thư Viện</button>
          <button class="btn-studio-action primary" onclick="store.showToast('Đã lưu mẫu khung 4 ô vào thư viện', 'success')">💾 Xuất Bản Mẫu</button>
        </div>
      </div>

      <div class="cockpit-split-2" style="grid-template-columns: 1fr 340px;">
        <!-- Canvas Designer 4 Slots -->
        <div class="cockpit-panel" style="display: flex; align-items: center; justify-content: center; background: #05070B; min-height: 520px;">
          <div style="width: 220px; height: 500px; background: #FFFFFF; border: 2px dashed #D4AF37; position: relative; padding: 8px; display: flex; flex-direction: column; gap: 6px;">
            <div style="flex: 1; border: 2px dashed #3B82F6; background: rgba(59, 130, 246, 0.1); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #3B82F6;">
              Slot #1 (Tọa độ: 8, 8, 204, 105)
            </div>
            <div style="flex: 1; border: 2px dashed #3B82F6; background: rgba(59, 130, 246, 0.1); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #3B82F6;">
              Slot #2 (Tọa độ: 8, 119, 204, 105)
            </div>
            <div style="flex: 1; border: 2px dashed #3B82F6; background: rgba(59, 130, 246, 0.1); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #3B82F6;">
              Slot #3 (Tọa độ: 8, 230, 204, 105)
            </div>
            <div style="flex: 1; border: 2px dashed #3B82F6; background: rgba(59, 130, 246, 0.1); display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; color: #3B82F6;">
              Slot #4 (Tọa độ: 8, 341, 204, 105)
            </div>
            <div style="height: 24px; display: flex; align-items: center; justify-content: center; font-size: 9px; font-weight: 800; color: #000;">
              1998 TEAM • LIFE4CUTS 2026
            </div>
          </div>
        </div>

        <!-- Thuộc tính tọa độ -->
        <div class="cockpit-panel">
          <div class="panel-header">
            <div class="panel-title">Thuộc Tính Khung & 4 Slots</div>
          </div>
          <div style="font-size: 13px; line-height: 1.8; margin-bottom: 16px;">
            • Khổ giấy xuất in: <b>2x6 inch (Dải dọc)</b><br>
            • Tổng số ô ảnh con: <b>4 Slots Độc Lập</b><br>
            • Tỷ lệ từng ô: <b>3:2 (Chuẩn cảm biến Nikon D780)</b><br>
            • Định dạng file overlay: <b>PNG 300 DPI Transparent</b>
          </div>
          <div style="background: var(--bg-card-subtle); padding: 12px; border-radius: var(--radius-btn); font-size: 12px; color: var(--text-muted);">
            💡 Frame Designer hoạt động độc lập, không làm xáo trộn luồng camera hay gián đoạn phiên chụp tại booth.
          </div>
        </div>
      </div>
    `;
  }

  // --------------------------------------------------------------------------
  // RENDER APP MAIN DISPATCHER
  // --------------------------------------------------------------------------

  function renderApp() {
    const s = store.getState();
    const container = document.getElementById("cockpit-main");

    if (s.mode === "kiosk") {
      renderKioskStages();
      return;
    }

    // Cập nhật Sidebar Navigation buttons active class
    document.querySelectorAll(".nav-item-btn").forEach(btn => {
      btn.classList.toggle("active", btn.dataset.view === s.activeView);
    });

    // Cập nhật tên sự kiện trên sidebar
    document.getElementById("sidebar-event-label").textContent = s.currentEvent.name;

    // Render View tương ứng
    switch (s.activeView) {
      case "dashboard": container.innerHTML = renderDashboard(); break;
      case "capture": container.innerHTML = renderCaptureStudio(); break;
      case "events": container.innerHTML = renderEvents(); break;
      case "templates": container.innerHTML = renderTemplates(); break;
      case "gallery": container.innerHTML = renderGallery(); break;
      case "printing": container.innerHTML = renderPrinting(); break;
      case "qr": container.innerHTML = renderQRSharing(); break;
      case "devices": container.innerHTML = renderDevices(); break;
      case "settings": container.innerHTML = renderSettings(); break;
      case "designer": container.innerHTML = renderDesigner(); break;
      default: container.innerHTML = renderDashboard();
    }
  }

  // --------------------------------------------------------------------------
  // KIOSK MODE CONTROLLER & STAGES (CONCEPT B — MODERN EVENT)
  // --------------------------------------------------------------------------

  function renderKioskStages() {
    const s = store.getState();
    const stages = ["kiosk-welcome", "kiosk-capture", "kiosk-review", "kiosk-final"];
    stages.forEach(id => {
      const el = document.getElementById(id);
      if (el) el.classList.remove("active");
    });

    // Cập nhật tiêu đề sự kiện Kiosk
    document.getElementById("kiosk-event-name").textContent = s.currentEvent.name;

    if (s.captureState === "idle") {
      document.getElementById("kiosk-welcome").classList.add("active");
    } else if (["countdown", "flash"].includes(s.captureState)) {
      document.getElementById("kiosk-capture").classList.add("active");
      updateKioskCaptureHUD();
    } else if (s.captureState === "review") {
      document.getElementById("kiosk-review").classList.add("active");
      updateKioskReviewDisplay();
    } else if (["printing", "finished"].includes(s.captureState)) {
      document.getElementById("kiosk-final").classList.add("active");
    }
  }

  function updateKioskCaptureHUD() {
    const s = store.getState();
    const countEl = document.getElementById("kiosk-countdown-num");
    if (countEl) countEl.textContent = s.countdownSeconds;

    const bannerEl = document.getElementById("retake-banner");
    const bannerText = document.getElementById("retake-banner-text");
    const isRetake = s.retakeSlotIndex !== -1;
    const activeSlotIdx = isRetake ? s.retakeSlotIndex : s.currentSlotIndex;
    const poseInfo = MOCK_DATA.slot_poses[activeSlotIdx] || MOCK_DATA.slot_poses[0];

    // Banner chụp lại riêng ô
    if (isRetake) {
      bannerEl.style.display = "flex";
      bannerText.textContent = `🔄 ĐANG CHỤP LẠI RIÊNG Ô SỐ ${activeSlotIdx + 1} (CÁC Ô 1, 3, 4 ĐƯỢC BẢO TOÀN NGUYÊN VẸN)`;
    } else {
      bannerEl.style.display = "none";
    }

    // Hướng dẫn tư thế chụp (Pose Guidance Overlay Box - Round 2.1 Refinement)
    const poseBadge = document.getElementById("kiosk-pose-badge");
    const poseTitle = document.getElementById("kiosk-pose-title");
    const poseTip = document.getElementById("kiosk-pose-tip");
    const viewImg = document.getElementById("kiosk-viewfinder-img");

    if (isRetake) {
      if (poseBadge) poseBadge.textContent = `🔄 CHỤP LẠI RIÊNG Ô SỐ ${activeSlotIdx + 1} / ${s.totalSlots}`;
      if (poseTitle) poseTitle.textContent = poseInfo.guide_retake || poseInfo.guide;
      if (poseTip) poseTip.textContent = poseInfo.subguide_retake || poseInfo.subguide;
      if (viewImg) viewImg.src = poseInfo.src_retaken || poseInfo.src_original;
    } else {
      if (poseBadge) poseBadge.textContent = `TƯ THẾ ${activeSlotIdx + 1} / ${s.totalSlots}`;
      if (poseTitle) poseTitle.textContent = poseInfo.guide;
      if (poseTip) poseTip.textContent = poseInfo.subguide;
      if (viewImg) viewImg.src = poseInfo.src_original;
    }

    // Danh sách 4 slot xem trước ở sidebar Kiosk
    const slotsContainer = document.getElementById("kiosk-sidebar-slots");
    slotsContainer.innerHTML = Array.from({length: s.totalSlots}).map((_, i) => {
      const slotData = s.capturedSlots[i];
      const isDone = slotData !== undefined;
      const isCurrent = (s.retakeSlotIndex !== -1) ? (i === s.retakeSlotIndex) : (i === s.currentSlotIndex);
      const poseDef = MOCK_DATA.slot_poses[i] || {};
      return `
        <div class="kiosk-slot-preview-card ${isDone ? 'captured' : ''} ${isCurrent ? 'active' : ''}">
          <span class="kiosk-slot-number-badge">ẢNH #${i + 1}</span>
          ${isDone ? `<img src="${slotData.src}" alt="Shot ${i+1}">` : `<span style="font-size: 20px; color: var(--text-muted); text-align: center; padding: 6px;">📷<br><span style="font-size: 10px; font-weight: 700;">${poseDef.pose_name || 'Ô ' + (i+1)}</span></span>`}
        </div>
      `;
    }).join('');
  }

  function updateKioskReviewDisplay() {
    const s = store.getState();
    const stageEl = document.getElementById("review-slots-stage");
    
    // Render 4 slots con riêng biệt với hình ảnh minh họa khác nhau
    stageEl.innerHTML = s.capturedSlots.map((slot, i) => `
      <div class="composite-slot-item">
        <img src="${slot.src}" alt="Slot ${i+1}">
        <span class="slot-tag-overlay ${slot.is_retaken ? 'retaken' : ''}">
          Ô #${i + 1} • ${slot.is_retaken ? 'ĐÃ CHỤP LẠI (MỚI)' : 'ẢNH GỐC'}
        </span>
        ${slot.is_retaken ? '<span class="slot-retaken-stamp">★ ĐÃ CHỤP LẠI (SLOT #' + (i + 1) + ')</span>' : ''}
        <button class="btn-slot-retake-overlay" onclick="triggerSlotRetake(${i})">
          🔄 Chụp Lại Ô #${i + 1}
        </button>
      </div>
    `).join('');

    // Cập nhật bảng kiểm định Slot Retake Audit Status khẳng định bảo toàn các ô khác
    const auditEl = document.getElementById("retake-audit-status");
    if (auditEl) {
      const slot2 = s.capturedSlots[1] || {};
      const isRetaken2 = slot2.is_retaken;
      auditEl.innerHTML = `
        <div style="font-size: 13px; font-weight: 800; color: var(--text-accent); margin-bottom: 6px;">
          📋 BẢNG KIỂM ĐỊNH BẢO TOÀN DỮ LIỆU TỪNG Ô (SLOT-BASED RETAKE AUDIT):
        </div>
        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 8px; font-size: 12px; margin-bottom: 8px;">
          <div>• <b>Ô #1:</b> <span style="color: #3B82F6; font-weight: 700;">[ẢNH GỐC - BẢO TOÀN]</span> (Vẫy tay chào)</div>
          <div>• <b>Ô #2:</b> ${isRetaken2 ? '<span style="color: #10B981; font-weight: 800;">[ĐÃ CHỤP LẠI - CẬP NHẬT]</span> (Bắn Tim ➜ Nháy Mắt)' : '<span style="color: #3B82F6; font-weight: 700;">[ẢNH GỐC - BẢO TOÀN]</span> (Bắn Tim)'}</div>
          <div>• <b>Ô #3:</b> <span style="color: #3B82F6; font-weight: 700;">[ẢNH GỐC - BẢO TOÀN]</span> (Cười tươi)</div>
          <div>• <b>Ô #4:</b> <span style="color: #3B82F6; font-weight: 700;">[ẢNH GỐC - BẢO TOÀN]</span> (Tạo dáng V-Sign)</div>
        </div>
        <div style="font-size: 11px; color: var(--text-muted); border-top: 1px dashed var(--border-subtle); padding-top: 6px;">
          🔒 <i>Cam kết hệ thống: Thao tác chụp lại ô #2 cập nhật chính xác slot 2 mà không ghi đè, không xoay vòng và không làm mất 3 ô còn lại.</i>
        </div>
      `;
    }
  }

  // --------------------------------------------------------------------------
  // INTERACTIVE 4-SLOT CAPTURE & SLOT RETAKE FLOWS
  // --------------------------------------------------------------------------

  window.startKioskMode = function() {
    store.setMode("kiosk");
  };

  // Khách bấm bắt đầu tại Kiosk Welcome
  window.triggerKioskStart = function() {
    store.setState({
      captureState: "countdown",
      currentSlotIndex: 0,
      capturedSlots: [],
      retakeSlotIndex: -1,
      countdownSeconds: 3
    });
    runCountdownStep();
  };

  function runCountdownStep() {
    let sec = 3;
    store.setState({ countdownSeconds: sec });

    // Phát âm thanh giọng đếm tiếng Việt
    playSound(audioVoice);

    const timer = setInterval(() => {
      sec--;
      if (sec > 0) {
        store.setState({ countdownSeconds: sec });
        playSound(audioTick);
      } else {
        clearInterval(timer);
        executeShotFlash();
      }
    }, 1000);
  }

  function executeShotFlash() {
    const s = store.getState();
    const flashEl = document.getElementById("kiosk-flash");
    flashEl.classList.add("flashing");

    // Phát âm thanh trập máy ảnh chính thức
    playSound(audioShutter);

    setTimeout(() => {
      flashEl.classList.remove("flashing");
      
      const newSlots = [...s.capturedSlots];
      const slotIndexToFill = s.retakeSlotIndex !== -1 ? s.retakeSlotIndex : s.currentSlotIndex;
      const poseDef = MOCK_DATA.slot_poses[slotIndexToFill] || MOCK_DATA.slot_poses[0];
      const isRetake = (s.retakeSlotIndex !== -1);

      // Gán đối tượng ảnh với hình ảnh riêng biệt theo từng tư thế
      newSlots[slotIndexToFill] = {
        slot_num: slotIndexToFill + 1,
        src: isRetake ? (poseDef.src_retaken || "assets/slot_2_pose_retaken_new.jpg") : poseDef.src_original,
        pose_name: isRetake ? (poseDef.pose_name_retaken || "Nháy Mắt Cá Tính (MỚI)") : poseDef.pose_name,
        is_retaken: isRetake,
        timestamp: new Date().toLocaleTimeString()
      };

      if (isRetake) {
        // KHẲNG ĐỊNH: Vừa hoàn tất Retake duy nhất 1 ô -> Trở lại Review ngay, bảo toàn các ô khác
        store.setState({
          capturedSlots: newSlots,
          captureState: "review",
          retakeSlotIndex: -1
        });
        store.showToast(`✅ Đã chụp lại thành công Ô #${slotIndexToFill + 1}! Các ô 1, 3, 4 được bảo toàn nguyên vẹn.`, "success");
      } else {
        const nextIndex = s.currentSlotIndex + 1;
        if (nextIndex < s.totalSlots) {
          store.setState({
            capturedSlots: newSlots,
            currentSlotIndex: nextIndex,
            countdownSeconds: 3
          });
          setTimeout(runCountdownStep, 900);
        } else {
          // Đã chụp đủ cả 4 ô -> Chuyển sang màn hình Review
          store.setState({
            capturedSlots: newSlots,
            captureState: "review"
          });
        }
      }
    }, 200);
  }

  // Khách chọn chụp lại 1 ô đơn lẻ (Slot Retake Demo: Ô 2)
  window.triggerSlotRetake = function(slotIndex) {
    store.setState({
      captureState: "countdown",
      retakeSlotIndex: slotIndex,
      countdownSeconds: 3
    });
    runCountdownStep();
  };

  // Khách chọn chụp lại toàn bộ 4 ô
  window.triggerRetakeAll = function() {
    store.setState({
      captureState: "countdown",
      currentSlotIndex: 0,
      capturedSlots: [],
      retakeSlotIndex: -1,
      countdownSeconds: 3
    });
    runCountdownStep();
  };

  // Khách chấp nhận ảnh và tiến hành in
  window.triggerAcceptAndPrint = function() {
    const s = store.getState();
    store.setState({
      captureState: "printing",
      paperRemaining: Math.max(0, s.paperRemaining - 2),
      sessionCount: s.sessionCount + 1,
      printCount: s.printCount + 2
    });

    let progress = 0;
    const prnTimer = setInterval(() => {
      progress += 25;
      if (progress >= 100) {
        clearInterval(prnTimer);
        store.setState({ captureState: "finished" });
        setTimeout(() => {
          if (store.getState().captureState === "finished") {
            store.setState({ captureState: "idle" });
          }
        }, 8000);
      }
    }, 600);
  };

  // --------------------------------------------------------------------------
  // BẢO MẬT KIOSK: BỘ ĐIỀU KHIỂN MÃ PIN & KHÓA AN TOÀN
  // --------------------------------------------------------------------------

  let secretClickCount = 0;
  let secretClickTimer = null;

  window.handleKioskSecretExit = function() {
    secretClickCount++;
    if (secretClickTimer) clearTimeout(secretClickTimer);

    if (secretClickCount >= 3) {
      secretClickCount = 0;
      openPinModal();
    } else {
      secretClickTimer = setTimeout(() => {
        secretClickCount = 0;
      }, 1000);
    }
  };

  window.openPinModal = function() {
    const s = store.getState();
    if (s.lockoutSeconds > 0) {
      store.showToast(`⛔ Hệ thống đang bị tạm khóa. Vui lòng thử lại sau ${s.lockoutSeconds}s`, "error");
      return;
    }

    store.setState({
      pinModalOpen: true,
      enteredPin: ""
    });

    document.getElementById("pin-modal").classList.add("active");
    updatePinDots();
  };

  window.closePinModal = function() {
    store.setState({ pinModalOpen: false, enteredPin: "" });
    document.getElementById("pin-modal").classList.remove("active");
  };

  function updatePinDots() {
    const s = store.getState();
    const dots = document.querySelectorAll("#pin-dots-container .pin-dot");
    dots.forEach((dot, idx) => {
      dot.classList.toggle("filled", idx < s.enteredPin.length);
    });
    const errorEl = document.getElementById("pin-error-msg");
    if (errorEl) errorEl.textContent = "";
  }

  window.appendPinKey = function(digit) {
    const s = store.getState();
    if (s.lockoutSeconds > 0 || s.enteredPin.length >= 4) return;

    const newPin = s.enteredPin + digit;
    store.setState({ enteredPin: newPin });
    updatePinDots();

    if (newPin.length === 4) {
      setTimeout(verifyPinSubmission, 200);
    }
  };

  window.deletePinKey = function() {
    const s = store.getState();
    if (s.enteredPin.length > 0) {
      store.setState({ enteredPin: s.enteredPin.slice(0, -1) });
      updatePinDots();
    }
  };

  function verifyPinSubmission() {
    const s = store.getState();
    if (s.enteredPin === s.adminPin) {
      closePinModal();
      openExitConfirmModal();
    } else {
      const modalBox = document.querySelector(".pin-modal-card");
      modalBox.classList.add("pin-shake");
      setTimeout(() => modalBox.classList.remove("pin-shake"), 400);

      const attempts = s.failedAttempts + 1;
      const errorEl = document.getElementById("pin-error-msg");
      
      if (attempts >= 3) {
        startLockoutCountdown(30);
        closePinModal();
        store.showToast("⛔ Đã nhập sai mã PIN 3 lần! Tạm khóa 30 giây để bảo mật booth.", "error");
      } else {
        store.setState({
          failedAttempts: attempts,
          enteredPin: ""
        });
        if (errorEl) {
          errorEl.textContent = `Mã PIN không đúng. Còn ${3 - attempts} lần thử.`;
        }
        updatePinDots();
      }
    }
  }

  function startLockoutCountdown(seconds) {
    store.setState({ lockoutSeconds: seconds, failedAttempts: 0 });
    const timer = setInterval(() => {
      const current = store.getState().lockoutSeconds;
      if (current <= 1) {
        clearInterval(timer);
        store.setState({ lockoutSeconds: 0 });
      } else {
        store.setState({ lockoutSeconds: current - 1 });
      }
    }, 1000);
  }

  window.openExitConfirmModal = function() {
    document.getElementById("exit-confirm-modal").classList.add("active");
  };

  window.cancelExitKiosk = function() {
    document.getElementById("exit-confirm-modal").classList.remove("active");
  };

  window.confirmExitKiosk = function() {
    document.getElementById("exit-confirm-modal").classList.remove("active");
    store.setMode("operator");
    store.showToast("Đã trở về Buồng Lái Vận Hành (Operator Mode)", "info");
  };

  // --------------------------------------------------------------------------
  // HÀM TIỆN ÍCH THỬ NGHIỆM TƯƠNG TÁC
  // --------------------------------------------------------------------------

  window.cycleDeviceState = function() {
    const states = ["CONNECTED", "CONNECTING", "BUSY", "WARNING", "ERROR", "DISCONNECTED"];
    const curIdx = states.indexOf(MOCK_DATA.devices.camera.state);
    const nextIdx = (curIdx + 1) % states.length;
    store.setCameraState(states[nextIdx]);
  };

  window.simulateTestCapture = function() {
    store.showToast("📸 Đã gửi lệnh chụp thử tới Nikon D780 (Shutter OK [MOCK])", "success");
    playSound(audioShutter);
  };

  window.simulateTestPrint = function() {
    store.showToast("🖨️ Đã gửi trang in test tới máy in nhiệt DNP DS-RX1HS [SIMULATED]", "info");
  };

  window.simulateFlashTest = function() {
    const flashEl = document.getElementById("studio-flash");
    if (flashEl) {
      flashEl.classList.add("flashing");
      playSound(audioShutter);
      setTimeout(() => flashEl.classList.remove("flashing"), 200);
    }
  };

  window.simulateVoiceTest = function() {
    playSound(audioVoice);
  };

  window.toggleMirror = function() {
    const feed = document.getElementById("studio-feed");
    if (feed) {
      const isMirrored = feed.style.transform === "scaleX(-1)";
      feed.style.transform = isMirrored ? "none" : "scaleX(-1)";
      store.showToast(isMirrored ? "Đã tắt chế độ lật gương" : "Đã bật chế độ lật gương (Mirror Mode)", "info");
    }
  };

  window.updateAdminPin = function() {
    const inp = document.getElementById("admin-pin-input");
    if (inp && inp.value.length >= 4) {
      store.setState({ adminPin: inp.value });
      store.showToast(`Đã đổi mã PIN thoát Kiosk thành: ${inp.value}`, "success");
    }
  };

  window.runSelfTest = function() {
    store.showToast("🩺 Đang chạy chẩn đoán toàn diện hệ thống...", "info");
    setTimeout(() => {
      store.showToast("✓ Hệ thống hoạt động tốt: Camera USB 3.0 OK, DNP Spooler OK, Hotspot 5G OK [SIMULATED]", "success");
    }, 1200);
  };

  window.setTemplateFilter = function(catId) {
    store.setState({ templateCategory: catId });
    renderApp();
  };

  window.reprintPhoto = function(sessionId) {
    store.showToast(`Đang in lại ảnh phiên: ${sessionId}...`, "info");
  };

  window.showQrForPhoto = function(sessionId) {
    store.showToast(`Mở mã QR cho phiên: ${sessionId}`, "info");
  };

  // Global Keybindings
  document.addEventListener("keydown", (e) => {
    if (e.key === "F11") {
      e.preventDefault();
      const s = store.getState();
      if (s.mode === "operator") {
        startKioskMode();
      } else {
        openPinModal();
      }
    }
  });

  // Gắn sự kiện chuyển tab Sidebar
  document.querySelectorAll(".nav-item-btn").forEach(btn => {
    btn.addEventListener("click", () => {
      store.setView(btn.dataset.view);
    });
  });

  // Gắn sự kiện Theme Switcher
  document.querySelectorAll(".btn-theme-choice").forEach(btn => {
    btn.addEventListener("click", () => {
      document.querySelectorAll(".btn-theme-choice").forEach(b => b.classList.remove("active"));
      btn.classList.add("active");
      store.setTheme(btn.dataset.theme);
    });
  });

  // Đăng ký render phản ứng
  store.subscribe(renderApp);

  // URL Query Params hỗ trợ kiểm thử và chụp screenshot tự động
  const urlParams = new URLSearchParams(window.location.search);
  const initialTheme = urlParams.get("theme") || "hybrid";
  const initialView = urlParams.get("view") || "dashboard";
  const initialMode = urlParams.get("mode") || "operator";
  const initialStage = urlParams.get("stage") || "idle";

  document.querySelectorAll(".btn-theme-choice").forEach(b => {
    b.classList.toggle("active", b.dataset.theme === initialTheme);
  });

  store.setTheme(initialTheme);
  if (initialMode === "kiosk") {
    store.setMode("kiosk");
    if (initialStage === "review") {
      // 4 ảnh minh họa riêng biệt với ô số 2 đã chụp lại để chụp screenshot minh họa rõ ràng
      store.setState({
        captureState: "review",
        capturedSlots: [
          { slot_num: 1, src: "assets/slot_1_pose_wave.jpg", pose_name: "Vẫy Tay Chào", is_retaken: false },
          { slot_num: 2, src: "assets/slot_2_pose_retaken_new.jpg", pose_name: "Nháy Mắt Cá Tính (Retaken New)", is_retaken: true },
          { slot_num: 3, src: "assets/slot_3_pose_smile.jpg", pose_name: "Cười Tươi Rạng Rỡ", is_retaken: false },
          { slot_num: 4, src: "assets/slot_4_pose_peace.jpg", pose_name: "Tạo Dáng V-Sign", is_retaken: false }
        ]
      });
    } else if (initialStage === "countdown") {
      store.setState({
        captureState: "countdown",
        countdownSeconds: 2,
        currentSlotIndex: 1,
        retakeSlotIndex: 1, // Đang chụp lại riêng ô 2
        capturedSlots: [
          { slot_num: 1, src: "assets/slot_1_pose_wave.jpg", pose_name: "Vẫy Tay Chào", is_retaken: false },
          { slot_num: 2, src: "assets/slot_2_pose_heart_old.jpg", pose_name: "Bắn Tim Nhí Nhảnh", is_retaken: false },
          { slot_num: 3, src: "assets/slot_3_pose_smile.jpg", pose_name: "Cười Tươi Rạng Rỡ", is_retaken: false },
          { slot_num: 4, src: "assets/slot_4_pose_peace.jpg", pose_name: "Tạo Dáng V-Sign", is_retaken: false }
        ]
      });
    } else {
      store.setState({ captureState: "idle" });
    }
  } else {
    store.setView(initialView);
  }

  renderApp();
});
