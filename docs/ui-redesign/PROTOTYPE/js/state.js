/**
 * 1998 TEAM PHOTOBOOTH — PROTOTYPE STATE MANAGER (ROUND 2.1 REFINED)
 * Quản lý trạng thái tương tác phản ứng (Reactive State Store)
 */

class StateStore {
  constructor() {
    this.state = {
      // Chế độ Hybrid: Operator là Concept A, Kiosk là Concept B
      theme: "hybrid", // hybrid | concept_a | concept_b | concept_c
      
      // Preset giao diện sự kiện của Kiosk (Wedding / Festival / Corporate)
      kioskThemePreset: "kiosk_theme_wedding",

      // Chế độ hiện tại: operator | kiosk
      mode: "operator",

      // Phân hệ đang mở trong Operator Mode
      activeView: "dashboard",

      // Sự kiện hiện tại
      currentEvent: MOCK_DATA.events.find(e => e.active) || MOCK_DATA.events[0],

      // Template hiện tại (Mặc định 4 ô chuẩn Hàn Quốc)
      currentTemplate: MOCK_DATA.templates.find(t => t.id === "tpl_cute_strip4") || MOCK_DATA.templates[0],

      // Danh mục template đang lọc
      templateCategory: "all",

      // Trạng thái phiên chụp Live Kiosk: idle | countdown | flash | review | printing | finished | error
      captureState: "idle",

      // Đếm ngược số giây hiện tại
      countdownSeconds: 3,

      // Tổng số slot cần chụp: 4 ô chuẩn theo chỉ đạo Round 2 & Round 2.1
      totalSlots: 4,

      // Slot đang chụp (0, 1, 2, 3)
      currentSlotIndex: 0,

      // Danh sách ảnh chụp cho từng slot: mảng 4 phần tử với 4 ảnh minh họa riêng biệt
      capturedSlots: [
        { slot_num: 1, src: "assets/slot_1_pose_wave.jpg", pose_name: "Vẫy Tay Chào", is_retaken: false, timestamp: "21:40:10" },
        { slot_num: 2, src: "assets/slot_2_pose_heart_old.jpg", pose_name: "Bắn Tim Nhí Nhảnh", is_retaken: false, timestamp: "21:40:22" },
        { slot_num: 3, src: "assets/slot_3_pose_smile.jpg", pose_name: "Cười Tươi Rạng Rỡ", is_retaken: false, timestamp: "21:40:35" },
        { slot_num: 4, src: "assets/slot_4_pose_peace.jpg", pose_name: "Tạo Dáng V-Sign", is_retaken: false, timestamp: "21:40:48" }
      ],

      // Slot đang được chọn để Retake riêng (-1 nếu chụp mới bình thường, 1 nếu chọn ô #2)
      retakeSlotIndex: -1,

      // Lượng giấy ảo còn lại trong máy in DNP [SIMULATED]
      paperRemaining: MOCK_DATA.devices.printer.paper_remaining,

      // Tiến trình in ảo (0 - 100%)
      printProgress: 0,

      // Bộ đếm phiên hôm nay [DEMO]
      sessionCount: 64,
      printCount: 128,

      // BẢO MẬT KIOSK NÂNG CẤP
      adminPin: "1998",        // Mã PIN quản trị (có thể đổi trong Cài đặt)
      enteredPin: "",          // Chuỗi nhập hiện tại (mã hóa dấu chấm tròn)
      pinModalOpen: false,     // Modal nhập PIN
      exitConfirmOpen: false,  // Modal xác nhận trước khi thoát Kiosk
      failedAttempts: 0,       // Số lần nhập sai liên tiếp
      lockoutSeconds: 0,       // Đếm ngược thời gian khóa (nếu sai 3 lần)

      // Toast thông báo hệ thống
      toastMessage: null,
      toastType: "info"
    };

    this.listeners = [];
  }

  getState() {
    return this.state;
  }

  setState(updates) {
    this.state = { ...this.state, ...updates };
    this.notify();
  }

  subscribe(listener) {
    this.listeners.push(listener);
    return () => {
      this.listeners = this.listeners.filter(l => l !== listener);
    };
  }

  notify() {
    for (const listener of this.listeners) {
      listener(this.state);
    }
  }

  setTheme(themeName) {
    this.setState({ theme: themeName });
    this.updateBodyClasses();
  }

  setMode(modeName) {
    if (["operator", "kiosk"].includes(modeName)) {
      this.setState({
        mode: modeName,
        captureState: "idle",
        retakeSlotIndex: -1,
        exitConfirmOpen: false,
        pinModalOpen: false
      });
      this.updateBodyClasses();
    }
  }

  setKioskThemePreset(presetId) {
    this.setState({ kioskThemePreset: presetId });
    this.updateBodyClasses();
  }

  updateBodyClasses() {
    const s = this.state;
    let themeClass = "theme-hybrid";
    if (s.theme !== "hybrid") {
      themeClass = `theme-${s.theme}`;
    }
    document.body.className = `${themeClass} mode-${s.mode} ${s.kioskThemePreset}`;
  }

  setView(viewId) {
    if (this.state.mode === "operator") {
      this.setState({ activeView: viewId });
    }
  }

  setEvent(eventId) {
    const evt = MOCK_DATA.events.find(e => e.id === eventId);
    if (evt) {
      MOCK_DATA.events.forEach(e => e.active = (e.id === eventId));
      this.setState({
        currentEvent: evt,
        kioskThemePreset: evt.kiosk_theme_preset || "kiosk_theme_wedding"
      });
      this.updateBodyClasses();
      this.showToast(`Đã kích hoạt sự kiện: ${evt.name}`, "success");
    }
  }

  setTemplate(templateId) {
    const tpl = MOCK_DATA.templates.find(t => t.id === templateId);
    if (tpl) {
      MOCK_DATA.templates.forEach(t => t.is_active = (t.id === templateId));
      this.setState({
        currentTemplate: tpl,
        totalSlots: tpl.slots_count
      });
      this.showToast(`Đã áp dụng mẫu khung: ${tpl.name} (${tpl.slots_count} ô)`, "success");
    }
  }

  setCameraState(newState) {
    const labels = {
      CONNECTED: "CONNECTED (SẴN SÀNG)",
      CONNECTING: "CONNECTING (ĐANG BẮT TAY PTP)",
      BUSY: "BUSY (ĐANG XẢ BUFFER SD)",
      WARNING: "WARNING (PIN YẾU / NHIỆT CAO)",
      ERROR: "ERROR (LỖI TRẬP / THẺ KHÓA)",
      DISCONNECTED: "DISCONNECTED (MẤT KẾT NỐI)"
    };
    const icons = {
      CONNECTED: "✓",
      CONNECTING: "⏳",
      BUSY: "⚡",
      WARNING: "⚠️",
      ERROR: "✕",
      DISCONNECTED: "✕"
    };

    MOCK_DATA.devices.camera.state = newState;
    MOCK_DATA.devices.camera.state_label = labels[newState] || newState;
    MOCK_DATA.devices.camera.state_icon = icons[newState] || "•";
    this.notify();
    this.showToast(`Camera State: ${MOCK_DATA.devices.camera.state_label}`, newState === "CONNECTED" ? "success" : "warning");
  }

  setPrinterState(newState) {
    const labels = {
      CONNECTED: "READY (SẴN SÀNG IN)",
      OUT_OF_PAPER: "OUT OF PAPER (HẾT CUỘN GIẤY)",
      SPOOLER_ERROR: "SPOOLER ERROR (LỖI HÀNG ĐỢI IN)",
      DISCONNECTED: "DISCONNECTED (MẤT CÁP USB)"
    };
    const icons = {
      CONNECTED: "✓",
      OUT_OF_PAPER: "⚠️",
      SPOOLER_ERROR: "✕",
      DISCONNECTED: "✕"
    };

    MOCK_DATA.devices.printer.state = newState;
    MOCK_DATA.devices.printer.state_label = labels[newState] || newState;
    MOCK_DATA.devices.printer.state_icon = icons[newState] || "•";
    this.notify();
    this.showToast(`Printer State: ${MOCK_DATA.devices.printer.state_label}`, newState === "CONNECTED" ? "success" : "warning");
  }

  showToast(msg, type = "info") {
    this.setState({ toastMessage: msg, toastType: type });
    setTimeout(() => {
      if (this.state.toastMessage === msg) {
        this.setState({ toastMessage: null });
      }
    }, 3500);
  }
}

const store = new StateStore();
