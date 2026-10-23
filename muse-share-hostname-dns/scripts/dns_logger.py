#!/usr/bin/env python3
"""Tiny UDP DNS server that logs every query. Answers A=127.0.0.1 for *.share.test and share.test."""
from __future__ import annotations
import socket, struct, threading, time
from pathlib import Path

LOG = Path(__file__).resolve().parents[1] / "results" / "dns-queries.log"
LOG.parent.mkdir(exist_ok=True)
HOST, PORT = "127.0.0.1", 5355
ANSWER_IP = "127.0.0.1"

def encode_name(name: str) -> bytes:
    out = b""
    for lab in name.rstrip(".").split("."):
        b = lab.encode("idna")
        out += bytes([len(b)]) + b
    return out + b"\x00"

def parse_name(data: bytes, offset: int):
    labels = []
    jumped = False
    start = offset
    while True:
        if offset >= len(data):
            raise ValueError("truncated")
        length = data[offset]
        if length == 0:
            offset += 1
            break
        if length & 0xC0 == 0xC0:
            if not jumped:
                start_next = offset + 2
            pointer = struct.unpack("!H", data[offset:offset+2])[0] & 0x3FFF
            offset = pointer
            jumped = True
            continue
        offset += 1
        labels.append(data[offset:offset+length].decode("ascii"))
        offset += length
    end = start_next if jumped else offset
    return ".".join(labels).lower(), end

def build_response(req: bytes) -> bytes:
    if len(req) < 12:
        return b""
    tid = req[:2]
    qname, qend = parse_name(req, 12)
    qtype, qclass = struct.unpack("!HH", req[qend:qend+4])
    with LOG.open("a") as f:
        f.write(f"{time.time():.3f}\t{qname}\tqtype={qtype}\n")
        f.flush()
    # Always answer A for our test zone
    flags = 0x8180  # standard response, recursion available
    header = tid + struct.pack("!HHHHH", flags, 1, 1, 0, 0)
    question = req[12:qend+4]
    # pointer to name at offset 12
    answer = struct.pack("!HHHLH", 0xC00C, 1, 1, 60, 4) + socket.inet_aton(ANSWER_IP)
    return header + question + answer

def main():
    LOG.write_text("")  # reset
    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((HOST, PORT))
    print(f"DNS logger on {HOST}:{PORT}, log={LOG}", flush=True)
    while True:
        data, addr = sock.recvfrom(4096)
        try:
            resp = build_response(data)
            if resp:
                sock.sendto(resp, addr)
        except Exception as e:
            print("err", e, flush=True)

if __name__ == "__main__":
    main()
