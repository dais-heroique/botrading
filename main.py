import argparse
from collector.solana import SolanaCollector, load_config

def main():
    p=argparse.ArgumentParser(); p.add_argument("--collect",action="store_true"); args=p.parse_args()
    if args.collect: SolanaCollector(load_config()).collect_once(); print("collection complete")
if __name__ == "__main__": main()
