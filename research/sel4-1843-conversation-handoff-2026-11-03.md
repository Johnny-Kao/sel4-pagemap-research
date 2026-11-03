# seL4 #1843 — 研究討論紀錄與暫停交接

日期：2026-11-03  
狀態：**PARKED / 暫停**  
Repository：`Johnny-Kao/sel4-pagemap-research`  
Branch：`research/device-region-alignment`  
Upstream：`seL4/seL4`；原 PR [#1843](https://github.com/seL4/seL4/pull/1843)，關聯已合併 PR [#1804](https://github.com/seL4/seL4/pull/1804)

> 本檔為本次對話的研究整理與恢復工作的交接紀錄，不是逐字聊天轉錄。包括使用者的疑問、分析、證據界線、對外溝通草稿與明確的暫停決策。**未獲使用者進一步明確指示，不建立或回覆任何 upstream Issue/PR、不提出 Patch、不做額外研究／測試、不刪除既有成果。**

## 1. 為什麼研究這件事

起點是以 invariant 檢查硬體初始化的區間與資源所有權：裝置 Device Tree `reg` 宣告的實體資源，經過 Hardware Generator 後，應如何影響 Kernel 的 MMIO mapping、reservation，以及初始任務 Device Untyped capabilities。

核心問題不是少算三個 byte 本身，而是**裝置資源範圍與 Kernel 所認定的擁有權是否一致**。如果非對齊來源區間的末端未納入保留資料，最終會否有原本應由 Kernel 獨占的裝置頁面被視為可分配？這是重要但目前未觀察到真實危害的風險假說。

seL4 是以能力（capability）管理存取權限的高保證微核心。Hardware Generator 是主機建置時執行的 Python 工具，不是在受限的 CPU/GPU 上執行；其輸出卻會進入嵌入式 Kernel 的初始化資料。核心形式化驗證也有 boot、硬體及 DMA 等信任前提。**不能由此直接推斷 seL4 已違反其所有安全保證。**

## 2. 已確定的計算缺陷

2019 年的 `tools/hardware/memory.py::Region.align_size`：

```python
new_base = hardware.utils.align_down(self.base, align_bits)
new_size = hardware.utils.align_up(self.size, align_bits)
return Region(new_base, new_size, self.owner)
```

原始 `[base,base+size)` 若起點未對齊，向下調整起點之後，長度沒有增加同等 offset，因此新區間可能不足以覆蓋原始區間。

以 4 KiB page 為例：
- 原始裝置 `[0x1003,0x2003)`
- 目前輸出 `[0x1000,0x2000)`
- 漏掉 `[0x2000,0x2003)` 的 3 bytes
- 完整涵蓋須 `[0x1000,0x3000)`，因此 mapping/reservation 的差異是一整個 4 KiB 頁面，**但不是資料被搬移或毀損 4 KiB**。

精確觸發條件（`size>0`）：設 `Q=page_size`，`o=base%Q`，`r=size%Q`，則
`o>0 && (r==0 || o+r>Q)`。

起點未對齊不一定有問題；短而沒有跨越邊界的裝置資源不觸發。漏掉的裝置原始範圍可能是少數 bytes，也可能是接近一頁，不限三 bytes。

`kernel_size` 是從 Device Tree 原始／轉譯後裝置起點計算的 byte 數，不是從頁面向下對齊後起點重新算；原始 2019 年程式有 `region.base - aligned.base` 的頁內 register-symbol offset，顯示已有處理非對齊 register 起點的設計。2019 年的 schema `max(kernel_size,region_size)` 文句與實作 `min` 並不一致，2026 #1804 修正為 `min`。歷史文件不應被當成沒有錯誤的權威解釋。

## 3. 2019 與 2026 的責任變化

- 2019 硬體 Generator 引入上述區間對齊邏輯，主要用於 Kernel 的裝置映射。
- 2026 [#1804](https://github.com/seL4/seL4/pull/1804) 區分 **mapped prefix** 與 **full-device reservation**；原因是 Kernel 可能只映射一小段裝置，卻仍須保留整個 Kernel 專用資源，避免剩餘部分交給 User Space。
- #1804 未引進算術漏算公式，但把 `Region.align_size` 再用於完整裝置保留，因此新的 owner/reservation invariant 也受既有邊界條件限制。

**可確認的是程式路徑與區間涵蓋缺陷；不能確認 2019 開發者故意少算以供 Bootloader、BIOS 或韌體救援使用。** 若要保留韌體資源，原理上應有獨立的明確 reserved-memory／平台機制。漏保留末端頁面不是可靠的安全預留。

## 4. 不修改任何程式時，可能出現的兩條失效路徑

### A. Kernel MMIO mapping 不完整

若 Kernel 真的需要存取因漏算而未映射的 register，可能產生地址轉譯 fault、初始化失敗或系統停滯；是否發生由硬體 register map、CPU 對齊規定及實際程式存取決定。不是三 bytes 自動被破壞，沒有已證實的 CPU／GPU freeze。

### B. Kernel-owned reservation 不完整

ARM/RISC-V 的 `map_kernel_devices()` 分別消費 `kernel_device_frames` 和 `kernel_device_reserved_regions`，後者呼叫 `reserve_region()`；`src/kernel/boot.c::create_untypeds()` 會從沒有被保留的實體區間建立 device-untyped capabilities。若漏掉的頁面未被其他 reservation 覆蓋、落在 `CONFIG_PADDR_USER_DEVICE_TOP` 的範圍、符合 untyped 的大小與對齊條件，就可能增加初始 root task 可用的 Device Untyped 範圍。若該頁含 Kernel 專用控制 register，且權限被進一步委派給低信任元件，才有潛在隔離／授權後果。

**這是條件性風險，不等於已證實錯發 Capability 或已發生越權存取。** 可能有其他 reservation、`user:true`、不會使用的裝置 register 或沒有受影響硬體等安全條件。

### 責任定位

如果通用 `reg` 格式和具體 binding 沒要求 page-aligned base，Generator 是否應保證完整涵蓋，或要在輸入邊界拒絕不支持的 layout？這是應交由上游確認的正式契約問題。不能直接宣布整個專案「失格」或核可的驗證已失效。

## 5. 已有的實證與限制

- 已追 `FdtParser.get_kernel_devices()`：只考慮 `/chosen/seL4,kernel-devices` 選中的裝置，並由硬體 YAML 規則挑選 `reg` index。
- 對 20 個既有 DTS/overlay 平台及 62 個被 Kernel 選中的裝置區間檢查：58 個 base 對齊、4 個未對齊、**0 個**觸發漏算；生成 C headers 與候選修改比較 **0 差異**。不等於所有已部署或未來硬體都安全。
- 真實未對齊起點包括 Raspberry Pi 4 UART、Odroid C2 UART、i.MX6 Sabre 的 timer/interrupt controller subregions。這表明「全面拒絕非對齊 base」與現有平台不相容。
- 合成 DTB 可以重現 Generator 漏算；早期 PL310 合成 fixture 缺少其 binding 需要的 `cache-unified`，後來已補正。但合成位址不是實際物理裝置存在的證明。
- Device Tree binding 一般不保證 page alignment；是否有特殊硬體要求仍需看實際 SoC 手冊、啟動流程、完整 binding。
- 尚無真實硬體 boot crash、錯誤發放能力、GPU/CPU freeze、資料外洩、正式部署受害案例。
- 研究及測試曾在 research branch 的 GitHub Actions 執行；未有 upstream patch/issue 輸出（原 PR #1843 已被關閉）。

Evidence:
- https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41629627065
- https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41623290788
- https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41634215423
- https://github.com/Johnny-Kao/sel4-pagemap-research/blob/research/device-region-alignment/research/sel4-1843-no-patch-failure-gates.md
- https://github.com/Johnny-Kao/sel4-pagemap-research/blob/research/device-region-alignment/research/sel4-1843-device-binding-deep-dive.md

## 6. 使用者對維護成本與對外溝通的決策

- 不為了取得一個 PR 而追求大量無硬體、無受影響部署證據的驗證。
- 目前不想打開 seL4 upstream Issue；先暫停，不急著提 Patch 或與 Maintainer 互動。
- 目前這份文件只供內部研究，**不要擅自發布**。
- 如果未來要討論，先用無背景 Maintainer 能看懂的語言說明「計算錯誤→漏映射／漏保留→條件性的資源授權風險」，不用指責原作者、猜測 freeze、宣稱形式化證明失效或保證零回歸。
- Maintainer 已在 #1843 表示不應直接送候選修法，應先用 Issue 解釋為何現在的行為是錯的，以及有何實際問題。
- 如果日後仍要做，應先明確定義投入上限和停損條件，避免為證明不可測的真實硬體後果不斷增加成本。
- **未得到使用者新指示前，維持 PARKED，不做任何後續操作、提交或刪除。**

## 7. 擬議 Issue（僅保留草稿，沒有發佈）

**Title: Device region alignment can leave part of a device unreserved**

I found a possible issue in how seL4 calculates the memory regions used by hardware devices.

When a device's starting address is not page-aligned, the hardware generator rounds the address down and the size up separately. This usually works, but in some cases the resulting region is too small.

For example, with 4 KiB pages:
- Actual device region: `0x1003–0x2003`
- Generated region: `0x1000–0x2000`

The last 3 bytes of the device are not covered.

The kernel uses these generated regions for mapping device registers and reserving hardware resources so they are not made available to user space.

If the generated region is too small, the kernel could miss part of a device it needs to access. Separately, part of a kernel-owned device might not be properly reserved. Depending on the hardware and other reservations, this could make an additional device page available through Device Untyped capabilities.

The calculation has existed since 2019. #1804 introduced the separate full-device reservation path that now also relies on it.

I checked 20 existing platform configurations covering 62 kernel device regions. None triggered the problem. I have not demonstrated a real hardware failure or security issue.

**Is this kind of device region valid input for the hardware generator, or does some platform/binding constraint make the current rounding sufficient?**

If valid, reservation should cover the entire kernel-owned device. If invalid, an explicit check could prevent future platforms from silently generating an incomplete region.

I am not proposing a patch before clarifying the expected behavior.

Research: https://github.com/Johnny-Kao/sel4-pagemap-research/actions/runs/41629627065

ChatGPT assisted with the source review and test preparation; I reviewed the findings.

## 8. Restart criteria (no automatic action)

Only on explicit user request, revisit (a) a supported/real physical device crossing page boundary; (b) whether the missing page really becomes a BootInfo Device Untyped; (c) whether a kernel register access uses the missing mapping; (d) fix safety for overlapping device pages, macros and mapping-window offsets; and (e) whether to file issue-first without proposing a patch.

**Current decision: PARK. Preserve work. No upstream contact or automatic follow-up.**
