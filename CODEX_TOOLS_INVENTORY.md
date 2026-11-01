# CODEX Tools Inventory — 1998 TEAM Photobooth

**Ngày kiểm tra:** 2026-11-01  
**Repository:** `C:\Users\Admin\Documents\photobooth`  
**Phạm vi:** Chỉ đọc nội dung thư mục, manifest và hướng dẫn; không cài đặt, sửa cấu hình hay source code.

## Tóm tắt

- `.agent/skills/` có **26 skill**: 25 workflow skill cũng có trong `agent-skills/skills/`, cộng `impeccable`.
- `agent-skills/skills/` có **25 skill**. Nội dung `SKILL.md` của các tên chung được đóng gói theo chuẩn Agent Skills, gồm YAML frontmatter `name`/`description` và phần hướng dẫn Markdown.
- `agent-skills/` có manifest Codex plugin (`.codex-plugin/plugin.json`) và marketplace (`.agents/plugins/marketplace.json`); tài liệu đi kèm nói Codex dùng trực tiếp `skills/` mà không cần chuyển đổi nội dung skill.
- Không tìm thấy file cấu hình MCP của project ở các vị trí thông dụng đã kiểm tra (`.mcp.json`, `mcp.json`, `.codex/config.toml`, `.gemini/settings.json`, `.vscode/mcp.json`, v.v.). Skill browser testing chỉ mô tả cấu hình Chrome DevTools MCP như yêu cầu tùy chọn, không phải cấu hình đang bật.
- Có `AGENTS.md` và `GEMINI.md` ở gốc. `GEMINI.md` chứa chỉ thị build/version/test dành cho agent, không phải cấu hình MCP. Không thấy cấu hình plugin Codex riêng ở gốc Photobooth.
- Trong `PATH` kiểm tra được `codex.exe`; không thấy `agy`, `gemini`, `claude` hoặc `antigravity`. Lệnh `codex --version` không cung cấp phiên bản vì CLI báo không tạo/thu dọn được thư mục tạm do Access Denied; vì vậy phiên bản CLI chưa được xác minh. Việc có binary Codex không chứng minh các plugin trong repo đã được cài/kích hoạt trong hồ sơ Codex.

## Agent Skills tìm thấy

Các mô tả dưới đây tóm tắt mục đích trong frontmatter của từng `SKILL.md`.

| Skill | Chức năng |
|---|---|
| `api-and-interface-design` | Thiết kế API, hợp đồng kiểu dữ liệu và ranh giới module ổn định. |
| `browser-testing-with-devtools` | Kiểm thử ứng dụng trên trình duyệt bằng Chrome DevTools MCP; cần MCP được cấu hình riêng. |
| `ci-cd-and-automation` | Thiết lập pipeline CI/CD, kiểm thử tự động và quality gates. |
| `code-review-and-quality` | Rà soát thay đổi theo nhiều tiêu chí chất lượng trước khi merge. |
| `code-simplification` | Làm gọn, dễ đọc và dễ bảo trì hơn mà vẫn giữ hành vi. |
| `constraint-driven-development` | Xác lập và bảo vệ chuẩn chất lượng/giới hạn của dự án. |
| `context-engineering` | Tổ chức context, hướng dẫn và quy tắc cho agent theo nhiệm vụ. |
| `debugging-and-error-recovery` | Tái hiện lỗi, khoanh vùng nguyên nhân gốc và thêm bảo vệ hồi quy. |
| `deprecation-and-migration` | Lập kế hoạch loại bỏ hệ thống cũ và chuyển đổi an toàn. |
| `documentation-and-adrs` | Ghi tài liệu kỹ thuật và quyết định kiến trúc cùng lý do. |
| `doubt-driven-development` | Đưa giả định/quyết định quan trọng qua phản biện độc lập. |
| `frontend-ui-engineering` | Xây dựng giao diện có chất lượng, responsive và accessibility. |
| `git-workflow-and-versioning` | Hướng dẫn nhánh, commit, PR, version và lịch sử Git. |
| `idea-refine` | Làm rõ ý tưởng qua quy trình mở rộng lựa chọn rồi hội tụ. |
| `impeccable` | Thiết kế/đánh giá/tinh chỉnh UI: UX, bố cục, màu, chữ, accessibility, responsive và hệ thống thiết kế; có launcher/reference riêng. |
| `incremental-implementation` | Triển khai theo lát nhỏ, có thể xác minh sau từng bước. |
| `interview-me` | Hỏi làm rõ mục tiêu khi yêu cầu còn mơ hồ trước khi lập kế hoạch. |
| `observability-and-instrumentation` | Thêm log, metric, trace và cảnh báo để hiểu hành vi lúc chạy. |
| `performance-optimization` | Đo và tối ưu hiệu năng dựa trên bottleneck đã xác định. |
| `planning-and-task-breakdown` | Chia yêu cầu/spec thành các nhiệm vụ có thứ tự và kiểm chứng được. |
| `security-and-hardening` | Giảm rủi ro bảo mật, xác thực dữ liệu và kiểm soát quyền truy cập. |
| `shipping-and-launch` | Chuẩn bị phát hành, theo dõi, rollout và phương án rollback. |
| `source-driven-development` | Đối chiếu tài liệu chính thức trước khi chọn cách triển khai. |
| `spec-driven-development` | Viết yêu cầu, phạm vi và tiêu chí chấp nhận trước khi code. |
| `test-driven-development` | Quy trình test đỏ → sửa cho xanh → refactor. |
| `using-agent-skills` | Skill điều phối: chọn workflow/skill phù hợp theo loại công việc. |

**Vị trí và số lượng:** `.agent/skills/*/SKILL.md`: 26; `agent-skills/skills/*/SKILL.md`: 25. 25 skill workflow dùng chung có tên tương ứng; `impeccable` chỉ có trong `.agent/skills/` của Photobooth. Bộ `agent-skills` còn có `agents/`, `commands/`, `.claude/`, `.gemini/`, `.opencode/`, `docs/`, `scripts/`, `hooks/`, nhưng các thành phần này không đồng nghĩa tất cả host đều hỗ trợ cùng một cách.

## Codex: dùng trực tiếp hay chuyển đổi?

### `agent-skills/`

Có thể dùng như **Codex plugin sau khi cài/kích hoạt**, không cần chuyển đổi nội dung `SKILL.md`: repo có `.codex-plugin/plugin.json` trỏ `skills` tới `./skills/` và `.agents/plugins/marketplace.json`; `docs/codex-setup.md` ghi quy trình đăng ký marketplace và cài plugin. Tài liệu repo nêu yêu cầu Codex CLI v0.122 trở lên. Đây là khả năng theo manifest/tài liệu; kiểm tra này **không cài plugin và không xác minh trạng thái plugin đang cài trong tài khoản Codex**.

Lệnh được tài liệu trong repo hướng dẫn (chỉ tham khảo, chưa chạy):

```text
codex plugin marketplace add C:\Users\Admin\Documents\photobooth\agent-skills
codex plugin add agent-skills@agent-skills
```

Hoặc đăng ký marketplace upstream rồi cài `agent-skills@agent-skills`; cách local clone tránh cần lấy nội dung skill từ xa. Sau cài đặt cần mở phiên Codex mới để discovery.

### `.agent/skills/`

Không có bằng chứng Codex tự nạp thư mục `.agent/skills/` của Photobooth. Codex plugin manifest hiện có nằm trong `agent-skills/`, và manifest đó chỉ trỏ `agent-skills/skills/`, không trỏ `.agent/skills/`. Các skill tương ứng có thể dùng qua plugin `agent-skills`; riêng `impeccable` cần cài bằng installer/marketplace dành cho Codex hoặc đưa vào vị trí skill Codex được hỗ trợ với metadata tương thích, thay vì kỳ vọng Codex tự nhận diện nó ở `.agent/skills/`.

### Kết quả thực tế của lần kiểm tra

- Đã đọc manifest và hướng dẫn, đếm skill files và xác định lệnh Codex có trong `PATH`.
- Không chạy lệnh cài đặt, không chạy setup, không thay đổi `settings.json`, MCP hay plugin.
- Chưa chứng minh được skill nào được nạp vào phiên Codex hiện tại; cần kiểm tra plugin catalog/skill picker sau khi người dùng quyết định cài.

## MCP server, plugin và công cụ AI trong repository

### Đã tìm thấy

- `agent-skills/.codex-plugin/plugin.json`: khai báo plugin Codex `agent-skills` phiên bản manifest `0.6.14`, `skills: ./skills/`.
- `agent-skills/.agents/plugins/marketplace.json`: marketplace local khai báo plugin source ở `./`.
- `agent-skills/.claude-plugin/`: manifest/marketplace cho Claude Code.
- `agent-skills/.gemini/commands/` và `commands/*.toml`: wrappers lệnh dạng TOML cho Gemini/host liên quan.
- `agent-skills/.opencode/`, `agents/`, `hooks/`, workflow CI: tích hợp/tiện ích cho một số host khác.
- `.agent/skills/impeccable/scripts/`: launcher Windows (`impeccable.cmd`), binary `impeccable.exe`, dữ liệu và tài liệu tham chiếu đi kèm; script ghi phiên bản `0.1.18`, còn frontmatter skill ghi `4.8.0`. Hai số này thuộc các thành phần/metadata khác nhau, không đủ căn cứ để kết luận binary đã được cập nhật hay tương thích Codex. Không chạy launcher.

### Không tìm thấy trong cấu hình project

- Không có cấu hình MCP đang khai báo server Photobooth/Chrome DevTools/REA trong các vị trí cấu hình project đã rà soát.
- Không có thư mục/plugin Codex ở gốc dự án Photobooth; metadata Codex nằm bên trong repo con `agent-skills/`.
- Không thấy skill REA trong hai thư mục skill của project.
- `browser-testing-with-devtools` nêu cần Chrome DevTools MCP; đây là hướng dẫn phụ thuộc môi trường, không phải một server đã cài hay bật.

Phạm vi kết luận MCP chỉ là cấu hình trong repository, không bao gồm cài đặt Codex/user-level MCP hoặc server đang kết nối từ ứng dụng Codex.

## Đánh giá tích hợp REA và Impeccable

### REA (Reverse Engineer Anything)

Không có REA skill hoặc MCP registration trong project. REA gồm hai phần riêng: workflow skill cho agent và MCP/CLI cung cấp công cụ phân tích. Cài skill đơn lẻ chỉ đưa hướng dẫn vào context, không tạo MCP server/công cụ. Tài liệu upstream hiện nêu `npx rea-agents setup` có thể đăng ký Codex và cài workflow tương ứng; sau đó cần khởi động phiên agent mới. Một số phân tích native còn cần Ghidra/Hopper/IDA; không phải tất cả workflow đều cần engine native. Tích hợp Codex khả thi, nhưng hiện chưa cấu hình/kiểm chứng trong Photobooth.

Khuyến nghị: nếu mục tiêu là phân tích artifact Nikon/MAID hoặc hành vi ứng dụng đóng gói, dùng hướng dẫn REA tương thích Codex **và** đăng ký MCP; trước khi chạy setup cần review đường dẫn/thay đổi nó đề xuất và chỉ cấp quyền cho client Codex. REA không cần thiết cho đọc kiến trúc source thông thường.

### Impeccable

Đã có nội dung skill Impeccable và binary Windows trong `.agent/skills/impeccable/`, nhưng chưa có bằng chứng Codex nhận diện skill này. Tài liệu chính thức Impeccable hiện hướng dẫn cài bằng `npx impeccable install`, chọn Codex và scope project/global, rồi reload; Codex gọi skill bằng `$impeccable`. Do đó có thể tích hợp mà không phải tự viết lại workflow, nhưng cần cài/cấu hình build riêng cho Codex và xác minh hook nếu muốn dùng tự động. Bản local trong `.agent/skills` khác với cách cài dành cho host; không nên mặc định nó đã được Codex hỗ trợ chỉ vì có `SKILL.md`.

## Đề xuất để Codex và Antigravity dùng chung hệ sinh thái

1. **Cài hai host riêng biệt trước:** Codex CLI/plugin và Antigravity CLI (`agy`). Hiện `codex.exe` được tìm thấy; `agy` không có trong `PATH`, nên chưa thể xác nhận Antigravity sẵn sàng trên máy này.
2. **Dùng `agent-skills/` làm nguồn workflow dùng chung:** cài plugin `agent-skills` vào từng host bằng cơ chế chính thức của từng host. Codex có plugin manifest riêng; Antigravity dùng `agy plugin install <đường-dẫn-local>` theo tài liệu trong repo. Nội dung skill Markdown có thể dùng chung; slash-command wrappers, agents, hooks và MCP config có thể cần cấu hình riêng theo host.
3. **Thêm Impeccable qua installer chọn provider Codex và Antigravity:** kiểm tra diff của những file/link/hook installer muốn tạo trước khi chấp nhận; hiện chỉ có bản skill local và binary, chưa xác minh các tích hợp host đã kích hoạt.
4. **Thêm REA chỉ khi có nhu cầu phân tích runtime/binary:** Node.js/npm là điều kiện của setup; dùng setup hỗ trợ Codex/Antigravity hoặc đăng ký local MCP server riêng cho từng client. Cần cấu hình từng client; cùng skill workflow không tự chia sẻ MCP registration.
5. **Dùng một nguồn kỹ năng và ghi rõ file host-specific:** tránh copy fork các workflow giữa host. Có thể giữ project policy ở `AGENTS.md`, nhưng rà soát riêng các chỉ thị trong `GEMINI.md` trước khi coi chúng là chính sách Codex/Antigravity; quy tắc build hiện có có thể không phù hợp với giới hạn phiên bản/phát hành của từng tác vụ.
6. **Xác minh sau khi cài:** mở session mới, liệt kê skill/plugin trong từng host, chạy một skill không thay đổi source (ví dụ review/plan) và kiểm tra riêng trạng thái MCP tools. Không coi việc file có mặt trong repo là bằng chứng đã được nạp.

Không cài đặt hoặc thay đổi nào trong các bước trên được thực hiện trong lần kiểm tra này.

## File đã đọc / cơ sở kiểm tra

- `AGENTS.md`, `GEMINI.md`
- `.agent/skills/*/SKILL.md`, `.agent/skills/impeccable/scripts/VERSION`
- `agent-skills/docs/codex-setup.md`, `agent-skills/docs/antigravity-setup.md`, `agent-skills/README.md`
- `agent-skills/.codex-plugin/plugin.json`, `agent-skills/.agents/plugins/marketplace.json`, `agent-skills/plugin.json`
- Candidate MCP/project config paths and references found by searching repository files.

## Nguồn bên ngoài đã đối chiếu

- [Agent Skills — Codex setup trong repository](https://github.com/addyosmani/agent-skills/blob/main/docs/codex-setup.md) (nội dung local tại `agent-skills/docs/codex-setup.md` được dùng cho trạng thái repo).
- [Agent Skills — Antigravity setup trong repository](https://github.com/addyosmani/agent-skills/blob/main/docs/antigravity-setup.md) (nội dung local tại `agent-skills/docs/antigravity-setup.md` được dùng cho trạng thái repo).
- [Impeccable official docs](https://impeccable.style/docs/) và [installation tutorial](https://impeccable.style/tutorials/getting-started/): Codex dùng `$impeccable`; installer chọn công cụ và cài bản tích hợp tương ứng.
- [REA upstream repository](https://github.com/morluto/rea): phân biệt skill hướng dẫn với MCP/CLI; setup hỗ trợ đăng ký client Codex và Antigravity.

## Giới hạn

Đây là inventory tĩnh. Không cài đặt/khởi chạy plugin, không sửa config, không kiểm tra user-level MCP servers đang chạy, không xác minh Codex plugin catalog trong UI và không xác minh Antigravity đã cài ngoài `PATH`.
