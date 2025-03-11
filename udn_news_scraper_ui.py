import streamlit as st
from datetime import date
import pandas as pd
import asyncio
import nest_asyncio
from UDNNewsScraper import UDNNewsScraper
import base64

# 啟用嵌套事件循環支持，讓 asyncio 可以在 Streamlit 中工作
nest_asyncio.apply()

# 創建下載連結的函數，不使用 st.download_button
def get_csv_download_link(df, filename="data.csv"):
    """生成 CSV 下載連結"""
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    csv_bytes = csv.encode('utf-8-sig')
    b64 = base64.b64encode(csv_bytes).decode()
    href = f'<a href="data:file/csv;base64,{b64}" download="{filename}" class="download-link">下載爬取資料</a>'
    return href

def main():
    st.title("UDN News Scraper")

    # 設置爬取參數
    keyword = st.text_input("請輸入關鍵字", "臺灣")
    
    # 日期選擇
    start_date = st.date_input("請選擇起始日期", value=date(2025, 1, 1))
    end_date = st.date_input("請選擇結束日期", value=date(2025, 3, 11))
    
    # 高級選項（可摺疊）
    with st.expander("進階設定"):
        headless = st.checkbox("不顯示瀏覽器", value=True)
        manual_mode = st.checkbox("手動登入模式", value=False)
        max_articles = st.number_input("最大爬取文章數", min_value=1, max_value=200, value=1)
    
    # 開始爬取的按鈕
    if st.button("開始爬取"):
        # 使用 Streamlit 提供的狀態元素，它們會自動更新
        status_text = st.empty()
        progress_bar = st.progress(0)
        article_status = st.empty()
        
        # 創建帶有進度更新的自定義回調
        class SimpleCallback:
            def __init__(self):
                self.current_stage = "初始化"
                self.current_page = 0
                self.total_pages = 1
                self.current_article = 0
                self.total_articles = 0
                self.latest_article = ""
            
            def stage_update(self, stage):
                self.current_stage = stage
                self._update_display()
            
            def page_update(self, current, total):
                self.current_page = current
                self.total_pages = total
                self._update_display()
            
            def article_update(self, current, total, title=""):
                self.current_article = current
                self.total_articles = total
                if title:
                    self.latest_article = title
                self._update_display()
            
            def _update_display(self):
                # 計算總體進度
                if self.total_articles > 0 and self.current_article > 0:
                    # 文章爬取階段
                    overall_progress = (self.current_article / self.total_articles)
                elif self.total_pages > 0 and self.current_page > 0:
                    # 頁面爬取階段
                    overall_progress = (self.current_page / self.total_pages) * 0.4  # 頁面階段佔40%進度
                else:
                    overall_progress = 0.1  # 初始階段
                
                # 更新狀態顯示
                progress_bar.progress(overall_progress)
                status_text.text(f"階段: {self.current_stage} | 頁面: {self.current_page}/{self.total_pages}")
                
                article_info = f"文章: {self.current_article}/{self.total_articles}"
                if self.latest_article:
                    article_info += f" | 最新: {self.latest_article[:30]}..."
                article_status.text(article_info)
        
        # 創建回調實例
        callback = SimpleCallback()
        callback.stage_update("開始爬取")
        
        with st.spinner("正在爬取文章..."):
            try:
                # 修改異步爬取函數調用
                async def run_scraper():
                    scraper = UDNNewsScraper(headless=headless)
                    try:
                        return await scraper.scrape(
                            keyword=keyword,
                            start_date=start_date.strftime('%Y-%m-%d'),
                            end_date=end_date.strftime('%Y-%m-%d'),
                            manual_mode=manual_mode,
                            max_articles=max_articles,
                            progress_callback=callback
                        )
                    finally:
                        await scraper.close()
                
                # 執行爬取
                df = asyncio.get_event_loop().run_until_complete(run_scraper())
                
                # 清除進度顯示
                status_text.empty()
                progress_bar.empty()
                article_status.empty()
                
                # 處理結果
                if not df.empty:
                    st.success(f"爬取成功！共獲取 {len(df)} 篇文章")
                    
                    # 創建區域分割，上面顯示預覽，下面顯示其他功能
                    col1, col2 = st.columns([3, 1])

                    # 顯示數據預覽
                    st.subheader("數據預覽")
                    st.dataframe(df.head(10))
                    
                    # 如果有超過 10 筆，顯示完整數據的選項
                    if len(df) > 10:
                        show_all = st.checkbox("顯示所有數據")
                        if show_all:
                            st.dataframe(df)

                    # 使用 HTML 下載連結代替 st.download_button
                    st.markdown(
                        get_csv_download_link(df, f"udn_{keyword}_新聞資料.csv"),
                        unsafe_allow_html=True
                    )
                    
                    # 添加一些 CSS 讓下載連結看起來像按鈕
                    st.markdown("""
                    <style>
                    .download-link {
                        background-color: transparent;
                        border: 1px solid #d6d6d8;
                        color: black !important;
                        padding: 10px 10px;
                        text-align: center;
                        text-decoration: none;
                        display: inline-block;
                        font-size: 16px;
                        margin: 2px 2px;
                        cursor: pointer;
                        border-radius: 12px;
                        text-decoration: none !important;
                        transition: all 0.15s ease;
                    }
                                
                    .download-link:hover {
                        border: 1px solid #ff4b4b;
                        color: #ff4b4b !important;
                    }
                    </style>
                    """, unsafe_allow_html=True)
                    
                    # 顯示一些統計信息
                    st.subheader("統計信息")
                    if 'Date' in df.columns:
                        # 按日期統計文章數量
                        date_counts = df['Date'].value_counts().sort_index()
                        st.bar_chart(date_counts)
                    
                else:
                    st.error("沒有抓取到任何資料！請嘗試不同的關鍵字或日期範圍。")
            
            except Exception as e:
                # 清除進度顯示
                status_text.empty()
                progress_bar.empty()
                article_status.empty()
                
                st.error(f"爬取過程中發生錯誤: {str(e)}")

if __name__ == "__main__":
    main()