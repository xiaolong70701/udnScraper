import subprocess
import os
import sys
import streamlit as st

def install_playwright_browsers():
    """安裝 Playwright 瀏覽器"""
    try:
        # 顯示安裝訊息
        st.info("正在安裝 Playwright 瀏覽器，這可能需要幾分鐘時間...")
        
        # 執行安裝命令
        result = subprocess.run(
            ["playwright", "install", "chromium"],
            capture_output=True,
            text=True,
            check=False
        )
        
        # 檢查安裝結果
        if result.returncode != 0:
            st.error(f"Playwright 瀏覽器安裝失敗: {result.stderr}")
            return False
        else:
            st.success("Playwright 瀏覽器安裝成功！")
            return True
    except Exception as e:
        st.error(f"Playwright 瀏覽器安裝過程中發生錯誤: {str(e)}")
        return False

# 檢查瀏覽器是否已安裝
def is_browser_installed():
    """檢查 Playwright 的 Chromium 瀏覽器是否已安裝"""
    # Playwright 的 Chromium 瀏覽器路徑
    browser_path = os.path.expanduser("~/.cache/ms-playwright/chromium-*/chrome-linux/chrome")
    
    # 使用 glob 模組查找匹配的路徑
    import glob
    browser_paths = glob.glob(browser_path)
    
    return len(browser_paths) > 0