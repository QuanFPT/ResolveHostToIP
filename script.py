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
    results = {}           # hostname -> set of ips (hoặc set rỗng nếu không resolve được)
    not_resolved = []

    print(f"Đang resolve với {args.threads} luồng...\n")

    with ThreadPoolExecutor(max_workers=args.threads) as executor:
        # submit với index để có thể theo dõi thứ tự nếu cần, nhưng thực tế dùng dict đơn giản hơn
        future_to_host = {executor.submit(resolve_hostname, hn): hn for hn in hostnames}
        
        for future in tqdm(as_completed(future_to_host), total=len(hostnames), desc="Progress"):
            hn = future_to_host[future]
            try:
                _, resolved_ips = future.result()
                results[hn] = resolved_ips
                if not resolved_ips:
                    not_resolved.append(hn)
            except Exception as e:
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
    # Xử lý output - giữ nguyên thứ tự trong file gốc
    if compare_mode:
        matching_lines = []
        for hn in hostnames:  # duyệt theo thứ tự gốc
            ips = results.get(hn, set())
            common = ips & target_ips
            if common:
                matching_lines.append((hn, common))

        if matching_lines:
            print("KẾT QUẢ MATCHING (theo thứ tự file gốc):")
            print("-" * 70)
            for hn, ips in matching_lines:
                ip_list = sorted(ips)  # chỉ sort IP, không sort hostname
                print(f"{hn:50} | {', '.join(ip_list)}")
            print("-" * 70)

            # Ghi file
            with output_file.open("w", encoding="utf-8") as f:
                f.write("# Hostname có ít nhất một IP trùng với danh sách mục tiêu\n")
                f.write("# Thứ tự theo file hostname gốc - Format: hostname:ip\n\n")
                for hn, ips in matching_lines:
                    for ip in sorted(ips):
                        f.write(f"{hn}:{ip}\n")
            
            print(f"\nĐã ghi {len(matching_lines)} hostname ({total_matches} dòng) → {output_file}")
        else:
            print("Không tìm thấy hostname nào có IP trùng với danh sách mục tiêu.")
    else:
        # Chế độ liệt kê tất cả
        resolved_lines = []
        for hn in hostnames:  # theo thứ tự gốc
            ips = results.get(hn, set())
            if ips:
                resolved_lines.append((hn, ips))

        if resolved_lines:
            print("KẾT QUẢ RESOLVE (theo thứ tự file gốc):")
            print("-" * 70)
            for hn, ips in resolved_lines:
                ip_list = sorted(ips)
                print(f"{hn:50} | {', '.join(ip_list)}")
            print("-" * 70)

            # Ghi file
            with output_file.open("w", encoding="utf-8") as f:
                f.write("# Kết quả resolve hostname → tất cả IPv4\n")
                f.write("# Thứ tự theo file hostname gốc - Format: hostname:ip\n\n")
                for hn, ips in resolved_lines:
                    for ip in sorted(ips):
                        f.write(f"{hn}:{ip}\n")
            
            total_ips = sum(len(ips) for _, ips in resolved_lines)
            print(f"\nĐã ghi {len(resolved_lines)} hostname ({total_ips} dòng) → {output_file}")
        else:
            print("Không có hostname nào resolve được IP.")

    # In hostname lỗi (vẫn giữ top 15 như cũ)
    if not_resolved:
        print("\nHostname KHÔNG RESOLVE ĐƯỢC (top 15):")
        for hn in not_resolved[:15]:
            print(f"  - {hn}")
        if len(not_resolved) > 15:
            print(f"  ... và {len(not_resolved)-15} hostname khác")


if __name__ == "__main__":
    main()
