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
        description="Resolve hostname → so sánh IP với target (multi-threaded) + ghi kết quả matching ra file"
    )
    parser.add_argument("--ip-file", required=True, help="File danh sách IP mục tiêu")
    parser.add_argument("--host-file", required=True, help="File danh sách hostname")
    parser.add_argument("--threads", type=int, default=100, help="Số luồng (default: 100)")
    parser.add_argument("--output", default="matching_results.txt", 
                        help="File output kết quả matching (default: matching_results.txt)")
    args = parser.parse_args()

    ip_file = Path(args.ip_file)
    host_file = Path(args.host_file)
    output_file = Path(args.output)

    # Đọc IP target
    if not ip_file.is_file():
        print(f"[!] Không tìm thấy file IP: {ip_file}")
        return

    target_ips = set()
    with ip_file.open(encoding="utf-8", errors="ignore") as f:
        for line in f:
            ip = line.strip()
            if ip and not ip.startswith(("#", "//")):
                target_ips.add(ip)

    print(f"[+] Đọc {len(target_ips)} IP từ {ip_file.name}")

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

    print(f"[+] Đọc {len(hostnames)} hostname từ {host_file.name}\n")

    # Kết quả
    matching = []  # list of (hostname, set_ips_trùng)
    not_resolved = []
    resolved_but_no_match = []

    print(f"Đang resolve với {args.threads} luồng...\n")

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        futures = [executor.submit(resolve_hostname, hn) for hn in hostnames]
        
        for future in tqdm(as_completed(futures), total=len(hostnames), desc="Progress"):
            hn, resolved_ips = future.result()
            
            if not resolved_ips:
                not_resolved.append(hn)
                continue

            common = resolved_ips & target_ips
            if common:
                matching.append((hn, common))
            else:
                resolved_but_no_match.append(hn)

    # Sắp xếp theo hostname
    matching.sort(key=lambda x: x[0])

    # Tóm tắt console
    print("\n" + "═" * 70)
    print(f" Tổng hostname xử lý     : {len(hostnames):3d}")
    print(f" → Có IP trùng khớp      : {len(matching):3d}")
    print(f" → Không resolve được    : {len(not_resolved):3d}")
    print(f" → Resolve OK nhưng không khớp : {len(resolved_but_no_match):3d}")
    print("═" * 70 + "\n")

    if matching:
        print("KẾT QUẢ MATCHING (in console):")
        print("-" * 60)
        for hn, ips in matching:
            ip_list = sorted(ips)
            print(f"{hn:50} | {', '.join(ip_list)}")
        print("-" * 60)

        # Ghi file output dạng host:ip
        with output_file.open("w", encoding="utf-8") as f:
            f.write("# Kết quả hostname có IP trùng với target\n")
            f.write("# Format: hostname:ip\n\n")
            for hn, ips in matching:
                for ip in sorted(ips):
                    f.write(f"{hn}:{ip}\n")
        
        print(f"\nĐã ghi {len(matching)} hostname ({sum(len(ips) for _, ips in matching)} dòng) vào file: {output_file}")
    else:
        print("Không có hostname nào khớp với danh sách IP mục tiêu.")

    if not_resolved and len(not_resolved) > 0:
        print("\nMột số hostname KHÔNG RESOLVE ĐƯỢC (top 15):")
        for hn in not_resolved[:15]:
            print(f"  - {hn}")
        if len(not_resolved) > 15:
            print(f"  ... và {len(not_resolved)-15} hostname khác")

if __name__ == "__main__":
    main()