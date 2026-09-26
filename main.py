"""Entrypoint for starting the Vera Message Engine server."""

import os
import uvicorn
from app.main import app


def main():
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run("app.main:app", host="0.0.0.0", port=port, reload=False)


if __name__ == "__main__":
    main()
