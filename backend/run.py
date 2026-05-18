"""AI-KTV 服务器入口"""
import os
import uvicorn

if __name__ == "__main__":
    is_dev = os.environ.get("ENV", "dev") == "dev"

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=is_dev,
        reload_dirs=["app"] if is_dev else None,
        workers=1,  # AI 模型需要在单进程内，不能用多 worker
    )
