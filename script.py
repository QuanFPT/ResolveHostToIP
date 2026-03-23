import socket
import argparse
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor, as_completed
from tqdm import tqdm

def resolve_hostname(hostname: str) -> tuple[str, set[str]]:
    try:
        addr_info = socket.getaddrinfo(hostname.strip(), None)
        ips = {info[4][0] for info in addr_info if info[0] == socket.AF_INET}
        return hostname, ips
    except (socket.gaierror, socket.herror, OSError):
        return hostname, set()


def main():
    parser = argparse.ArgumentParser(
        description="Resolve hostname → so sánh IP với target (nếu có) hoặc chỉ liệt kê IP"
    )
    parser.add_argument("--ip-file", required=False, 
                        help="File danh sách IP mục tiêu (tùy chọn)")
    parser.add_argument("--host-file", required=True, 
                        help="File danh sách hostname")
    parser.add_argument("--threads", type=int, default=100, 
                        help="Số luồng (default: 100)")
    parser.add_argument("--output", default="results.txt", 
                        help="File output kết quả (default: results.txt)")
    args = parser.parse_args()

    host_file = Path(args.host_file)
    output_file = Path(args.output)

    # Đọc hostname
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

    # Kết quả
    matching = []           # (hostname, set_ips_trùng)   — chỉ dùng khi compare
    all_resolved = []       # (hostname, set_ips)        — dùng khi không compare
    not_resolved = []

    print(f"Đang resolve với {args.threads} luồng...\n")

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = [executor.submit(resolve_hostname, hn) for hn in hostnames]
        
        for future in tqdm(as_completed(futures), total=len(hostnames), desc="Progress"):
            hn, resolved_ips = future.result()
            
            if not resolved_ips:
                not_resolved.append(hn)
                continue

            if compare_mode:
                common = resolved_ips & target_ips
                if common:
                    matching.append((hn, common))
                # else: bỏ qua (không lưu vào resolved_but_no_match nữa)
            else:
                all_resolved.append((hn, resolved_ips))

    # Sắp xếp theo hostname
    if compare_mode:
        matching.sort(key=lambda x: x[0])
    else:
        all_resolved.sort(key=lambda x: x[0])

    # ────────────────────────────────────────────────
    # In tóm tắt
    print("\n" + "═" * 70)
    print(f" Tổng hostname xử lý     : {len(hostnames):3d}")
    print(f" → Không resolve được    : {len(not_resolved):3d}")

    if compare_mode:
        print(f" → Có IP trùng khớp      : {len(matching):3d}")
        total_matches = sum(len(ips) for _, ips in matching)
        print(f" → Tổng dòng match       : {total_matches:3d}")
    else:
        print(f" → Resolve thành công    : {len(all_resolved):3d}")
    print("═" * 70 + "\n")

    # ────────────────────────────────────────────────
    # Xử lý output
    if compare_mode:
        if matching:
            print("KẾT QUẢ MATCHING (các hostname có IP trùng):")
            print("-" * 70)
            for hn, ips in matching:
                ip_list = sorted(ips)
                print(f"{hn:50} | {', '.join(ip_list)}")
            print("-" * 70)

            # Ghi file: host:ip
            with output_file.open("w", encoding="utf-8") as f:
                f.write("# Hostname có ít nhất một IP trùng với danh sách mục tiêu\n")
                f.write("# Format: hostname:ip\n\n")
                for hn, ips in matching:
                    for ip in sorted(ips):
                        f.write(f"{hn}:{ip}\n")
            
            print(f"\nĐã ghi {len(matching)} hostname ({total_matches} dòng) → {output_file}")
        else:
            print("Không tìm thấy hostname nào có IP trùng với danh sách mục tiêu.")
    else:
        # Chế độ liệt kê tất cả
        if all_resolved:
            print("KẾT QUẢ RESOLVE (tất cả hostname có IP):")
            print("-" * 70)
            for hn, ips in all_resolved:
                ip_list = sorted(ips)
                print(f"{hn:50} | {', '.join(ip_list)}")
            print("-" * 70)

            # Ghi file: host:ip (mọi IP)
            with output_file.open("w", encoding="utf-8") as f:
                f.write("# Kết quả resolve hostname → tất cả IPv4\n")
                f.write("# Format: hostname:ip\n\n")
                for hn, ips in all_resolved:
                    for ip in sorted(ips):
                        f.write(f"{hn}:{ip}\n")
            
            total_ips = sum(len(ips) for _, ips in all_resolved)
            print(f"\nĐã ghi {len(all_resolved)} hostname ({total_ips} dòng) → {output_file}")
        else:
            print("Không có hostname nào resolve được IP.")

    # In một phần hostname lỗi (nếu có)
    if not_resolved:
        print("\nHostname KHÔNG RESOLVE ĐƯỢC (top 15):")
        for hn in not_resolved[:15]:
            print(f"  - {hn}")
        if len(not_resolved) > 15:
            print(f"  ... và {len(not_resolved)-15} hostname khác")


if __name__ == "__main__":
    main()
