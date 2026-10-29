"""Download versioned RefSeq CDS FASTA files and verify the original bytes."""

import argparse
import gzip
import hashlib
import json
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from urllib.request import Request, urlopen

from .catalog import ROOT


def acquire(directory: Path, *, mirror: str | None = None) -> list[Path]:
    directory.mkdir(parents=True, exist_ok=True)
    sources = json.loads((ROOT / "generation/sources.json").read_text())

    def download(source):
        path = directory / (source["accession"] + ".fna.gz")
        if path.exists():
            data = gzip.decompress(path.read_bytes())
            if hashlib.sha256(data).hexdigest() == source["sha256"]:
                return path
            raise ValueError(f"Cached source checksum mismatch: {path}")
        url = source["url"] if mirror is None else mirror.rstrip("/") + "/" + path.name
        for attempt in range(3):
            try:
                with urlopen(
                    Request(url, headers={"User-Agent": "CDS-bench/0.1"}), timeout=120
                ) as response:
                    data = gzip.decompress(response.read())
                break
            except Exception:
                if attempt == 2:
                    raise
                time.sleep(2**attempt)
        if hashlib.sha256(data).hexdigest() != source["sha256"]:
            raise ValueError(
                f"NCBI annotation changed for {source['accession']}; use the frozen release mirror."
            )
        # mtime=0 makes the local compressed snapshot byte-reproducible too.
        path.write_bytes(gzip.compress(data, mtime=0))
        print(f"Acquired {source['accession']}", flush=True)
        return path

    with ThreadPoolExecutor(max_workers=3) as executor:
        return list(executor.map(download, sources))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, default=ROOT / "build/sources")
    parser.add_argument(
        "--mirror", help="Frozen source URL directory, when the upstream annotation changed"
    )
    args = parser.parse_args()
    acquire(args.directory, mirror=args.mirror)


if __name__ == "__main__":
    main()
