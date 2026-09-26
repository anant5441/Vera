"""Entrypoint for starting the Vera Message Engine server."""

import uvicorn
from app.main import app


def main():
    uvicorn.run("app.main:app", host="0.0.0.0", port=8080, reload=False)


if __name__ == "__main__":
    main()
