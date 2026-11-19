"""python -m radar.app [--puerto 8000]: abre la app en http://localhost:8000."""

import argparse
import logging

import uvicorn

PUERTO = 8000


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--puerto", type=int, default=PUERTO)
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    uvicorn.run("radar.app.api:app", host="127.0.0.1", port=args.puerto)


if __name__ == "__main__":
    main()
