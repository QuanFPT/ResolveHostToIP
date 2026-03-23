import socket
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm
import pandas as pd  # ← thêm dòng này

def resolve_hostname(hostname: str) -> tuple[str, set[str]]:
    try:
        addr_info = socket.getaddrinfo(hostname.strip(), None)
        ips = {info[4][0] for info in addr_info if info[0] == socket.AF_INET}
        return hostname, ips
    except (socket.gaierror, socket.herror, OSError):
        return hostname, set()


def main():
    parser = argparse.ArgumentParser(
        description="Resolve hostname → so sánh IP với target (nếu có) hoặc liệt kê IP → xuất Excel"
    )
    parser.add_argument("--ip-file", required=False, 
                        help="File danh sách IP mục tiêu (tùy chọn)")
    parser.add_argument("--host-file", required=True, 
                        help="File danh sách hostname")
    parser.add_argument("--threads", type=int, default=100, 
                        help="Số luồng (default: 100)")
    parser.add_argument("--output", default="results.xlsx", 
                        help="File output Excel (default: results.xlsx)")
    args = parser.parse_args()

    host_file = Path(args.host_file)
    output_file = Path(args.output)
    
    # Đảm bảo đuôi file là .xlsx
    if output_file.suffix.lower() != '.xlsx':
        output_file = output_file.with_suffix('.xlsx')

    # Đọc hostname - giữ nguyên thứ tự
    if not host_file.is_file():
        print(f"[!] Không tìm thấy file hostname: {host_file}")
        return

    hostnames = []
    with host_file.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            hn = line.strip()
            if hn and not hn.startswith(("#", "//")):
                hostnames.append(hn)

    print(f"[+] Đọc {len(hostnames)} hostname từ {host_file.name}")

    # Đọc IP target (nếu có)
    target_ips = set()
    compare_mode = bool(args.ip_file)

    if compare_mode:
        ip_file = Path(args.ip_file)
        if not ip_file.is_file():
            print(f"[!] Không tìm thấy file IP: {ip_file}")
            return

        with ip_file.open(encoding="utf-8", errors="ignore") as f:
            for line in f:
                ip = line.strip()
                if ip and not ip.startswith(("#", "//")):
                    target_ips.add(ip)

        print(f"[+] Đọc {len(target_ips)} IP mục tiêu từ {ip_file.name}")
        print("→ Chế độ: Tìm hostname có IP trùng khớp\n")
    else:
        print("→ Chế độ: Liệt kê tất cả IP của từng hostname (không so sánh)\n")

    # Lưu kết quả theo thứ tự hostname gốc
    results = {}           # hostname -> set of ips
    not_resolved = []

    print(f"Đang resolve với {args.threads} luồng...\n")

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        future_to_host = {executor.submit(resolve_hostname, hn): hn for hn in hostnames}
        
        for future in tqdm(as_completed(future_to_host), total=len(hostnames), desc="Progress"):
            hn = future_to_host[future]
            try:
                _, resolved_ips = future.result()
                results[hn] = resolved_ips
                if not resolved_ips:
                    not_resolved.append(hn)
            except Exception:
                results[hn] = set()
                not_resolved.append(hn)

    # ────────────────────────────────────────────────
    # In tóm tắt
    print("\n" + "═" * 70)
    print(f" Tổng hostname xử lý     : {len(hostnames):3d}")
    print(f" → Không resolve được    : {len(not_resolved):3d}")

    if compare_mode:
        match_count = sum(1 for ips in results.values() if ips & target_ips)
        total_matches = sum(len(ips & target_ips) for ips in results.values())
        print(f" → Có IP trùng khớp      : {match_count:3d}")
        print(f" → Tổng dòng match       : {total_matches:3d}")
    else:
        resolved_count = sum(1 for ips in results.values() if ips)
        print(f" → Resolve thành công    : {resolved_count:3d}")
    print("═" * 70 + "\n")

    # ────────────────────────────────────────────────
    # Chuẩn bị dữ liệu cho Excel
    data = []

    if compare_mode:
        for hn in hostnames:
            ips = results.get(hn, set())
            common = ips & target_ips
            if common:
                for ip in sorted(common):
                    data.append({"Hostname": hn, "IP": ip})
        
        if data:
            print(f"Đã chuẩn bị {len(data)} dòng dữ liệu (chỉ IP trùng) → xuất Excel")
        else:
            print("Không có hostname nào khớp với danh sách IP mục tiêu → file Excel sẽ rỗng")
    else:
        for hn in hostnames:
            ips = results.get(hn, set())
            if ips:
                for ip in sorted(ips):
                    data.append({"Hostname": hn, "IP": ip})
        
        if data:
            total_ips = len(data)
            print(f"Đã chuẩn bị {total_ips} dòng dữ liệu → xuất Excel")
        else:
            print("Không có hostname nào resolve được IP → file Excel sẽ rỗng")

    # ────────────────────────────────────────────────
    # Xuất Excel
    if data:
        df = pd.DataFrame(data)
        df.to_excel(output_file, index=False, engine='openpyxl')
        print(f"Đã xuất file Excel: {output_file}")
        print(f"→ Số dòng dữ liệu: {len(df)}")
        print(f"→ Số hostname có dữ liệu: {df['Hostname'].nunique()}")
    else:
        # Tạo file rỗng có header để người dùng biết
        df_empty = pd.DataFrame(columns=["Hostname", "IP"])
        df_empty.to_excel(output_file, index=False, engine='openpyxl')
        print(f"Đã tạo file Excel rỗng (chỉ có header): {output_file}")

    # In hostname lỗi (top 15)
    if not_resolved:
        print("\nHostname KHÔNG RESOLVE ĐƯỢC (top 15):")
        for hn in not_resolved[:15]:
            print(f"  - {hn}")
        if len(not_resolved) > 15:
            print(f"  ... và {len(not_resolved)-15} hostname khác")


if __name__ == "__main__":
    main()
