/**
 * 1998 TEAM PHOTOBOOTH — PROTOTYPE MOCK DATA (ROUND 2.1 REFINED)
 * Dữ liệu giả lập thực tế phục vụ thử nghiệm tương tác toàn diện
 * Hỗ trợ quy chuẩn Hybrid Design: Operator Concept A + Kiosk Concept B + Status Concept C
 * 
 * LƯU Ý QUAN TRỌNG:
 * Mọi số liệu và trạng thái trong tệp này đều là [DEMO / SIMULATED] phục vụ kiểm thử UI/UX,
 * không giả mạo là kết quả đọc trực tiếp từ phần cứng Nikon D780 hay DNP DS-RX1HS.
 */

const MOCK_DATA = {
  // Trạng thái phần cứng giả lập (Concept C: Multi-Channel Icon + Text Label + Telemetry + Border)
  devices: {
    camera: {
      model: "Nikon D780 (DSLR Full-Frame)",
      backend: "Nikon MAID3 Type0026 SDK + WPD Native",
      connection: "USB 3.0 Tethering (High-Speed PTP)",
      state: "CONNECTED", // CONNECTED | CONNECTING | BUSY | WARNING | ERROR | DISCONNECTED
      state_label: "CONNECTED (SẴN SÀNG)",
      state_icon: "✓",
      battery: 92, // [SIMULATED]
      shutter_count: 14820, // [SIMULATED]
      storage_free_mb: 58400, // [SIMULATED]
      live_view_fps: 29.8, // [SIMULATED]
      sensor_temp: "34°C [MOCK]",
      lens: "AF-S NIKKOR 50mm f/1.8G",
      aperture: "f/2.8 [MOCK]",
      shutter_speed: "1/160s [MOCK]",
      iso: "400 [MOCK]",
      white_balance: "Flash (5500K) [MOCK]",
      metering: "Matrix [MOCK]",
      focus_mode: "AF-S [SIMULATED AF TRACKING]"
    },
    printer: {
      model: "DNP DS-RX1HS (Dye-Sublimation)",
      driver: "DNP High-Speed Photoprinter Driver v2.1",
      connection: "USB 2.0 High-Speed Dedicated",
      state: "CONNECTED", // CONNECTED | OUT_OF_PAPER | SPOOLER_ERROR | DISCONNECTED
      state_label: "READY (SẴN SÀNG IN)",
      state_icon: "✓",
      paper_name: "4x6 inch (10x15cm) Roll",
      paper_remaining: 486, // [SIMULATED METRIC]
      paper_total: 700,
      ribbon_remaining_pct: 69, // [SIMULATED METRIC]
      head_temp: "38°C (Bình thường) [MOCK]",
      pacing_delay: "1.8s (Thermal Protection Pacing)",
      safety_margin: "98% (Fit-to-print Anti-Crop)"
    },
    network: {
      hotspot_name: "1998_TEAM_PHOTOBOOTH_5G",
      server_ip: "192.168.4.1",
      port: 8080,
      state: "CONNECTED",
      state_label: "BROADCASTING (PHÁT SÓNG)",
      state_icon: "✓",
      connected_clients: 4, // [SIMULATED]
      download_url: "http://192.168.4.1:8080/dl"
    }
  },

  // Danh mục 4 tư thế chuẩn cho phiên chụp 4 ô kèm hình ảnh minh họa riêng biệt
  slot_poses: [
    {
      slot_index: 0,
      slot_num: 1,
      guide: "Tư thế 1: Vẫy tay chào bạn bè 👋",
      subguide: "Nở nụ cười rạng rỡ và vẫy tay chào ống kính nào!",
      src_original: "assets/slot_1_pose_wave.jpg",
      pose_name: "Vẫy Tay Chào",
      tone_color: "#EA580C"
    },
    {
      slot_index: 1,
      slot_num: 2,
      guide: "Tư thế 2: Bắn tim nhí nhảnh 🫰",
      guide_retake: "Tư thế 2 mới: Nháy mắt cá tính & Chu môi 😉✨",
      subguide: "Tạo hình ngón tay bắn tim siêu ngọt ngào!",
      subguide_retake: "Biểu cảm nháy mắt tinh nghịch, chu môi độc đáo!",
      src_original: "assets/slot_2_pose_heart_old.jpg",
      src_retaken: "assets/slot_2_pose_retaken_new.jpg",
      pose_name: "Bắn Tim Nhí Nhảnh",
      pose_name_retaken: "Nháy Mắt Cá Tính (Retaken New)",
      tone_color: "#E11D48"
    },
    {
      slot_index: 2,
      slot_num: 3,
      guide: "Tư thế 3: Cười thật tươi rạng rỡ 😄",
      subguide: "Cười hết cỡ khoe trọn nụ cười xinh!",
      src_original: "assets/slot_3_pose_smile.jpg",
      pose_name: "Cười Tươi Rạng Rỡ",
      tone_color: "#D97706"
    },
    {
      slot_index: 3,
      slot_num: 4,
      guide: "Tư thế 4: Tạo dáng V-Sign cá tính ✌️",
      subguide: "Giơ 2 ngón tay chữ V phong cách Hàn Quốc!",
      src_original: "assets/slot_4_pose_peace.jpg",
      pose_name: "Tạo Dáng V-Sign",
      tone_color: "#7C3AED"
    }
  ],

  // Danh sách sự kiện (Events List)
  events: [
    {
      id: "evt_001",
      name: "Đám Cưới Minh & Linh",
      date: "2026-11-01",
      location: "Trung Tâm Tiệc Cưới White Palace, TP.HCM",
      active: true,
      total_sessions: 64, // [DEMO]
      total_prints: 128,   // [DEMO]
      active_template_id: "tpl_cute_strip4", // Mặc định 4 ô chuẩn yêu cầu Round 2
      kiosk_theme_preset: "kiosk_theme_wedding",
      storage_folder: "D:/1998Photobooth_Data/Events/DamCuoi_MinhLinh",
      notes: "Sự kiện tiệc cưới lãng mạn. Khách thích chụp 4 ô dọc lấy liền."
    },
    {
      id: "evt_002",
      name: "Gala Tech Summit 2026",
      date: "2026-11-05",
      location: "Trung Tâm Hội Nghị Quốc Gia, Hà Nội",
      active: false,
      total_sessions: 0,
      total_prints: 0,
      active_template_id: "tpl_corp_4x6",
      kiosk_theme_preset: "kiosk_theme_corporate",
      storage_folder: "D:/1998Photobooth_Data/Events/Gala_Tech_Summit",
      notes: "Sự kiện doanh nghiệp, khung ngang 4x6 in logo nhà tài trợ."
    },
    {
      id: "evt_003",
      name: "Sinh Nhật 20 Tuổi Hoàng Yến",
      date: "2026-10-28",
      location: "Sky Lounge Landmark 81",
      active: false,
      total_sessions: 82,
      total_prints: 164,
      active_template_id: "tpl_cute_strip4",
      kiosk_theme_preset: "kiosk_theme_festival",
      storage_folder: "D:/1998Photobooth_Data/Events/SinhNhat_HoangYen",
      notes: "Đã hoàn thành. Đạt 100% đánh giá 5 sao."
    }
  ],

  // Các Preset giao diện Kiosk linh hoạt theo loại sự kiện
  kiosk_theme_presets: [
    {
      id: "kiosk_theme_festival",
      name: "🌸 Trẻ Trung / Festival (Hồng San Hô & Tím Pastel)",
      class_name: "kiosk-theme-festival",
      bg_color: "#FFF5F7",
      accent_color: "#E11D48",
      card_bg: "#FFFFFF"
    },
    {
      id: "kiosk_theme_wedding",
      name: "💍 Tiệc Cưới / Lãng Mạn (Trắng Kem & Vàng Gold Nhẹ)",
      class_name: "kiosk-theme-wedding",
      bg_color: "#FDFBF7",
      accent_color: "#D4AF37",
      card_bg: "#FFFFFF"
    },
    {
      id: "kiosk_theme_corporate",
      name: "🏢 Doanh Nghiệp / Gala (Tối Giản Hiện Đại & Xanh Navy)",
      class_name: "kiosk-theme-corporate",
      bg_color: "#0F172A",
      accent_color: "#38BDF8",
      card_bg: "#1E293B"
    }
  ],

  // Thư viện Template khung ảnh (Frame Templates Library)
  templates: [
    {
      id: "tpl_cute_strip4",
      name: "Hàn Quốc 4 Ô Dọc (Life4Cuts 4-Strip Standard)",
      category: "cartoon",
      category_name: "🌸 4 Ô Chuẩn Hàn Quốc",
      layout_type: "1x4_strip",
      aspect_ratio: "1:4",
      slots_count: 4, // 4 slots bắt buộc phục vụ Slot-based Retake demo
      dimensions_mm: "50x152mm (2x6 inch)",
      print_media: "Single Strip",
      thumbnail: "assets/slot_1_pose_wave.jpg",
      is_active: true,
      description: "Khung 4 ô chuẩn Hàn Quốc với 4 tư thế riêng biệt, hỗ trợ chụp lại từng ô con độc lập."
    },
    {
      id: "tpl_wedding_2x6",
      name: "Dải Đôi Tiệc Cưới 4 Ô (Wedding Dual 4-Strip)",
      category: "wedding",
      category_name: "💍 Đám Cưới",
      layout_type: "2x6_dual",
      aspect_ratio: "2:6",
      slots_count: 4,
      dimensions_mm: "50x152mm (2x6 inch x 2)",
      print_media: "Cut 2-inch DNP Roll",
      thumbnail: "assets/slot_2_pose_heart_old.jpg",
      is_active: false,
      description: "Bố cục dải đôi 4 ô cắt tự động, viền vàng champagne và hoa văn ren tinh tế."
    },
    {
      id: "tpl_corp_4x6",
      name: "Kỷ Niệm Doanh Nghiệp (Corporate Postcard)",
      category: "corporate",
      category_name: "🏢 Doanh Nghiệp",
      layout_type: "4x6_postcard",
      aspect_ratio: "4:6",
      slots_count: 1,
      dimensions_mm: "100x152mm (4x6 inch)",
      print_media: "Standard Postcard",
      thumbnail: "assets/slot_3_pose_smile.jpg",
      is_active: false,
      description: "Khung khổ bưu thiếp 4x6 inch trang trọng, 1 ảnh tập thể lớn kèm banner sự kiện phía dưới."
    },
    {
      id: "tpl_minimal_grid4",
      name: "Tối Giản 4 Ô Vuông (Nordic 2x2 Grid)",
      category: "minimal",
      category_name: "✨ Tối Giản 2x2",
      layout_type: "2x2_grid",
      aspect_ratio: "1:1",
      slots_count: 4,
      dimensions_mm: "100x100mm (Square)",
      print_media: "Square 4x4",
      thumbnail: "assets/slot_4_pose_peace.jpg",
      is_active: false,
      description: "Bố cục 4 ô vuông 2x2 phong cách nghệ thuật đương đại, viền mỏng thanh lịch."
    },
    {
      id: "tpl_vintage_film",
      name: "Phim Nhựa Cổ Điển 4 Ô (Vintage 35mm Strip)",
      category: "vintage",
      category_name: "🎞️ Cổ Điển 4 Ô",
      layout_type: "1x4_strip",
      aspect_ratio: "1:4",
      slots_count: 4,
      dimensions_mm: "50x152mm (2x6 inch)",
      print_media: "Single Strip",
      thumbnail: "assets/slot_2_pose_retaken_new.jpg",
      is_active: false,
      description: "Mô phỏng cuộn phim nhựa Kodak 35mm 4 ô với tông màu hạt film hoài niệm thập niên 90."
    }
  ],

  // Danh mục phân loại template
  categories: [
    { id: "all", name: "Tất Cả Khung", icon: "📑" },
    { id: "cartoon", name: "4 Ô Hàn Quốc", icon: "🌸" },
    { id: "wedding", name: "Đám Cưới", icon: "💍" },
    { id: "corporate", name: "Doanh Nghiệp", icon: "🏢" },
    { id: "minimal", name: "Tối Giản 2x2", icon: "✨" },
    { id: "vintage", name: "Cổ Điển / Film", icon: "🎞️" }
  ],

  // Thư viện ảnh mẫu trong sự kiện (Gallery Photos 4-slot)
  gallery: [
    {
      id: "photo_064",
      session_id: "SES-20261101-064",
      timestamp: "21:42:15",
      composite_url: "assets/slot_2_pose_retaken_new.jpg",
      slots_count: 4,
      raw_slots: [
        "assets/slot_1_pose_wave.jpg",
        "assets/slot_2_pose_retaken_new.jpg",
        "assets/slot_3_pose_smile.jpg",
        "assets/slot_4_pose_peace.jpg"
      ],
      retake_history: "Slot #2 được chụp lại lúc 21:42:01 (Bắn Tim ➜ Nháy Mắt)",
      print_status: "printed",
      copies: 2,
      qr_code_url: "assets/slot_1_pose_wave.jpg",
      client_name: "Khách Bàn VIP 02"
    },
    {
      id: "photo_063",
      session_id: "SES-20261101-063",
      timestamp: "21:38:02",
      composite_url: "assets/slot_1_pose_wave.jpg",
      slots_count: 4,
      raw_slots: [
        "assets/slot_1_pose_wave.jpg",
        "assets/slot_2_pose_heart_old.jpg",
        "assets/slot_3_pose_smile.jpg",
        "assets/slot_4_pose_peace.jpg"
      ],
      retake_history: "Bảo toàn cả 4 ô gốc (Không chụp lại)",
      print_status: "printed",
      copies: 2,
      qr_code_url: "assets/slot_2_pose_heart_old.jpg",
      client_name: "Nhóm Bạn Cô Dâu"
    },
    {
      id: "photo_062",
      session_id: "SES-20261101-062",
      timestamp: "21:32:40",
      composite_url: "assets/slot_3_pose_smile.jpg",
      slots_count: 4,
      raw_slots: [
        "assets/slot_1_pose_wave.jpg",
        "assets/slot_2_pose_heart_old.jpg",
        "assets/slot_3_pose_smile.jpg",
        "assets/slot_4_pose_peace.jpg"
      ],
      retake_history: "Bảo toàn cả 4 ô gốc",
      print_status: "printed",
      copies: 2,
      qr_code_url: "assets/slot_3_pose_smile.jpg",
      client_name: "Gia Đình Chú Rể"
    }
  ],

  // Hàng đợi in (Print Spooler Queue)
  print_queue: [
    { id: "prn_098", session: "SES-064", copies: 2, status: "completed", time: "21:42:45", progress: 100 },
    { id: "prn_097", session: "SES-063", copies: 2, status: "completed", time: "21:38:30", progress: 100 },
    { id: "prn_096", session: "SES-062", copies: 2, status: "completed", time: "21:33:05", progress: 100 }
  ]
};
