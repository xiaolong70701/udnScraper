import re
import time
import math
import asyncio
import pandas as pd
from playwright.async_api import async_playwright
from tqdm import tqdm

class UDNNewsScraper:
    """
    Class for scraping news articles from UDN News website using Playwright Async API
    """

    def __init__(self, headless=False):
        """
        Initialize the UDN News Scraper

        Args:
            headless (bool): Whether to run the browser in headless mode
        """
        self.headless = headless
        self.browser = None
        self.page = None
        self.playwright = None
        self.base_url = "https://udndata.com"  # 基礎 URL
        self.progress_callback = None  # 進度回調

    async def _setup_driver(self):
        """
        Set up Playwright and return a page instance.

        Returns:
            tuple: (page, browser) instances
        """
        # Use async_playwright()
        self.playwright = await async_playwright().start()
        self.browser = await self.playwright.chromium.launch(headless=self.headless)
        self.page = await self.browser.new_page()
        return self.page, self.browser

    async def _fetch_article_content(self, link, index, total):
        """
        Fetch content from a single article

        Args:
            link: Article link URL
            index: Article index
            total: Total number of articles

        Returns:
            dict: Dictionary containing title, date, and content
        """
        try:
            # 確保 link 是絕對 URL
            if link.startswith('/'):
                link = f"{self.base_url}{link}"
            elif not link.startswith('http'):
                link = f"{self.base_url}/{link}"
                
            # 更新進度 - 文章標題暫未知
            if self.progress_callback:
                self.progress_callback.article_update(index, total)
                
            # print(f"\nProcessing article {index}/{total}: {link}")

            # Open the article page
            try:
                await self.page.goto(link, timeout=30000)  # 增加超時時間到 30 秒
                await asyncio.sleep(2)
            except Exception as nav_error:
                print(f"Navigation error: {nav_error}")
                return {
                    'Title': f"Article {index} (navigation failed)",
                    'Date': "Unknown date",
                    'Content': f"Content extraction failed: {str(nav_error)}"
                }

            # Extract news ID from the URL
            news_id = "Unknown ID"
            try:
                news_id_match = re.search(r'news_id=(\d+)', link)
                if news_id_match:
                    news_id = news_id_match.group(1)
                else:
                    alt_id_match = re.search(r'/(\d+)$', link)
                    if alt_id_match:
                        news_id = alt_id_match.group(1)
            except Exception as id_error:
                print(f"Error extracting news ID: {id_error}")

            # Extract title
            try:
                title_element = await self.page.query_selector("h1")
                title = await title_element.inner_text() if title_element else f"Article {index} (title extraction failed)"
                
                # 更新進度 - 包含實際標題
                if self.progress_callback:
                    self.progress_callback.article_update(index, total, title)
            except:
                title = f"Article {index} (title extraction failed)"

            # Extract date
            try:
                date_element = await self.page.query_selector("span.story-source")
                date_text = await date_element.inner_text() if date_element else "Unknown date"
                date_match = re.search(r'(\d{4}-\d{2}-\d{2})', date_text)
                article_date = date_match.group(1) if date_match else "Unknown date"
            except:
                article_date = "Unknown date"

            # Extract content
            try:
                content = ""
                selectors = [
                    "article",
                    "div.article",
                    "div.content",
                    "div.story"
                ]
                
                for selector in selectors:
                    content_element = await self.page.query_selector(selector)
                    if content_element:
                        paragraphs = await content_element.query_selector_all("p")
                        content_parts = []
                        for p in paragraphs:
                            p_text = await p.inner_text()
                            if p_text:
                                content_parts.append(p_text)
                        content = "\n".join(content_parts)
                        if content:
                            break

                if not content:
                    body_element = await self.page.query_selector("body")
                    content = await body_element.inner_text() if body_element else "Content extraction failed"
            except:
                content = "Content extraction failed"

            return {
                'News ID': news_id,
                'Title': title,
                'Date': article_date,
                'Content': content
            }
        except Exception as e:
            print(f"Error processing article: {e}")
            return {
                'Title': f"Article {index} (processing failed)",
                'Date': "Unknown date",
                'Content': f"Content extraction failed: {str(e)}"
            }

    async def scrape(self, keyword, start_date, end_date, output_file=None, manual_mode=False, max_pages=None, max_articles=50, progress_callback=None):
        """
        Main scraping method to fetch news articles based on search criteria

        Args:
            keyword (str): Search keyword
            start_date (str): Start date in yyyy-mm-dd format
            end_date (str): End date in yyyy-mm-dd format
            output_file (str): Output CSV filename
            manual_mode (bool): Whether to enable manual login mode
            max_pages (int): Maximum number of pages to scrape
            max_articles (int): Maximum number of articles to scrape
            progress_callback: Optional callback for progress updates

        Returns:
            DataFrame: Pandas DataFrame containing the scraped news data
        """
        # 保存進度回調
        self.progress_callback = progress_callback
        
        # Initialize Playwright and browser
        page, browser = await self._setup_driver()

        # List to store news data
        news_data = []

        try:
            # 更新進度 - 開始階段
            if self.progress_callback:
                self.progress_callback.stage_update("打開 UDN 新聞網站")
                
            # Open UDN search page
            full_url = f"{self.base_url}/ndapp/Index?cp=udn"
            print(f"Opening URL: {full_url}")
            await page.goto(full_url)
            print("Opened UDN News search page")

            # Click on the "IP Login" link
            try:
                if self.progress_callback:
                    self.progress_callback.stage_update("嘗試登入")
                    
                login_link = await page.query_selector("a:has-text('定址登入')")
                if login_link:
                    await login_link.click()
                    print("Clicked '定址登入' link")

                    # Wait for the manual login if required
                    if manual_mode:
                        if self.progress_callback:
                            self.progress_callback.stage_update("等待手動登入")
                            
                        print("Please complete the login process in the browser and press Enter to continue...")
                        # 使用 asyncio 的方式等待用戶輸入
                        await asyncio.to_thread(input)

                    # Wait for the page to load after login
                    await asyncio.sleep(3)
                else:
                    print("Login link not found, skipping login process.")
            except Exception as e:
                print(f"Error when clicking 'IP Login': {e}")
                print("Continuing with search process...")

            # Return to search page (if redirected to another page after login)
            if self.progress_callback:
                self.progress_callback.stage_update("輸入搜尋條件")
                
            await page.goto(f"{self.base_url}/ndapp/Index?cp=udn")

            # Enter search keyword
            search_input = await page.query_selector("#SearchString")
            await search_input.fill(keyword)
            print(f"Entered keyword: {keyword}")

            # Enter start date
            start_date_input = await page.query_selector("#datepicker-start")
            await start_date_input.fill(start_date)

            # Enter end date
            end_date_input = await page.query_selector("#datepicker-end")
            await end_date_input.fill(end_date)

            # Click the search button
            if self.progress_callback:
                self.progress_callback.stage_update("執行搜尋")
                
            submit_button = await page.query_selector("button[name='submit']")
            await submit_button.click()
            print("Clicked search button")

            # Wait for results page to load
            await asyncio.sleep(5)

            # Get total result count and calculate total pages
            if self.progress_callback:
                self.progress_callback.stage_update("分析搜尋結果")
                
            result_message = await page.query_selector("div.message")
            result_text = await result_message.inner_text() if result_message else ""
            
            # 獲取頁面原始碼檢查總結果數
            page_content = await page.content()
            total_results_match = re.search(r'共搜尋到\s*<span class="mark">(\d+)</span>筆資料', page_content)
            total_results = int(total_results_match.group(1)) if total_results_match else 0
            
            # 計算需要的頁數
            # 修改：如果 max_articles < 20，只抓取一頁
            if max_articles < 20:
                calculated_pages = 1
                print(f"max_articles ({max_articles}) < 20, only scraping the first page")
            else:
                calculated_pages = math.ceil(min(total_results, max_articles) / 20)
            
            # 應用 max_pages 限制（如果有指定）
            if max_pages is not None and max_pages > 0:
                total_pages = min(calculated_pages, max_pages)
            else:
                total_pages = calculated_pages

            # 顯示頁數計算的詳細信息
            print(f"Total results: {total_results}, Max articles: {max_articles}, Calculated pages: {calculated_pages}, Final total pages: {total_pages}")
            
            # Store all news links and titles
            news_links = []

            # 更新進度 - 開始抓取頁面
            if self.progress_callback:
                self.progress_callback.stage_update("抓取文章連結")
                self.progress_callback.page_update(0, total_pages)
            
            # 處理每一頁結果
            for current_page in range(1, total_pages + 1):
                # 更新進度 - 當前頁面
                if self.progress_callback:
                    self.progress_callback.page_update(current_page, total_pages)
                    
                if current_page > 1:
                    # Navigate to next page
                    current_url = page.url
                    if 'page=' in current_url:
                        next_page_url = re.sub(r'page=\d+', f'page={current_page}', current_url)
                    else:
                        separator = '&' if '?' in current_url else '?'
                        next_page_url = f"{current_url}{separator}page={current_page}"
                    
                    print(f"Navigating to page {current_page}: {next_page_url}")
                    await page.goto(next_page_url)
                    await asyncio.sleep(3)

                # Get news links and titles from current page
                title_elements = await page.query_selector_all("h2.control-pic a")
                for title_element in title_elements:
                    title = await title_element.inner_text()
                    link = await title_element.get_attribute('href')
                    
                    # 確保連結是絕對 URL
                    if link and link.startswith('/'):
                        link = f"{self.base_url}{link}"
                    
                    # print(f"Found article: {title} - {link}")
                    news_links.append((title, link))
                    
                    # 如果已經收集到足夠的連結，提前退出收集循環
                    if len(news_links) >= max_articles:
                        print(f"Collected {len(news_links)} links, which is enough for max_articles={max_articles}. Stopping collection.")
                        break
                
                # 如果已經收集到足夠的連結，提前退出頁面循環
                if len(news_links) >= max_articles:
                    break

            # 確保不超過 max_articles
            news_links = news_links[:min(len(news_links), max_articles)]
            print(f"Total links collected: {len(news_links)}")

            # 更新進度 - 開始抓取文章內容
            if self.progress_callback:
                self.progress_callback.stage_update("抓取文章內容")
                self.progress_callback.article_update(0, len(news_links))
                
            # 抓取每篇文章內容
            for index, (title, link) in enumerate(news_links, 1):
                try:
                    article_data = await self._fetch_article_content(link, index, len(news_links))
                    news_data.append(article_data)
                except Exception as e:
                    print(f"Error processing news: {e}")
                    news_data.append({
                        'Title': title,
                        'Date': "Unknown date",
                        'Content': f"Content extraction failed: {str(e)}"
                    })

            # 更新進度 - 處理結果
            if self.progress_callback:
                self.progress_callback.stage_update("處理爬取結果")

            # Create DataFrame and save to CSV if output file is specified
            if news_data:
                df = pd.DataFrame(news_data)
                if output_file:
                    df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"\nSuccessfully saved {len(news_data)} articles to {output_file}")
                return df
            else:
                print("No news content extracted")
                return pd.DataFrame(columns=['Title', 'Date', 'Content'])

        except Exception as e:
            print(f"Error occurred: {e}")
            if news_data:
                df = pd.DataFrame(news_data)
                if output_file:
                    df.to_csv(output_file, index=False, encoding='utf-8-sig')
                    print(f"Saved partial data ({len(news_data)} articles) to {output_file}")
                return df
            return pd.DataFrame(columns=['Title', 'Date', 'Content'])

        finally:
            # 更新進度 - 完成
            if self.progress_callback:
                self.progress_callback.stage_update("完成爬取")
                
            if self.browser:
                await self.browser.close()
                print("Browser closed")
            if self.playwright:
                await self.playwright.stop()

    async def close(self):
        """Close the browser if still open"""
        if self.browser:
            await self.browser.close()
        if self.playwright:
            await self.playwright.stop()
        print("Browser closed")

# 新增一個執行主函數的函數
async def run_scraper(keyword, start_date, end_date, output_file=None, manual_mode=False, max_pages=None, max_articles=50, headless=False, progress_callback=None):
    """
    運行爬蟲的主函數，方便在 Jupyter 中調用

    Args:
        keyword (str): 搜尋關鍵字
        start_date (str): 開始日期，格式為 yyyy-mm-dd
        end_date (str): 結束日期，格式為 yyyy-mm-dd
        output_file (str): 輸出的 CSV 檔案名稱
        manual_mode (bool): 是否啟用手動登入模式
        max_pages (int): 最多抓取的頁數
        max_articles (int): 最多抓取的文章數
        headless (bool): 是否啟用無頭模式
        progress_callback: 進度回調物件

    Returns:
        DataFrame: 包含爬取的新聞資料的 Pandas DataFrame
    """
    scraper = UDNNewsScraper(headless=headless)
    try:
        return await scraper.scrape(
            keyword=keyword,
            start_date=start_date,
            end_date=end_date,
            output_file=output_file,
            manual_mode=manual_mode,
            max_pages=max_pages,
            max_articles=max_articles,
            progress_callback=progress_callback
        )
    finally:
        await scraper.close()

# 提供一個同步的接口，方便在非異步環境中調用
def scrape_news(keyword, start_date, end_date, output_file=None, manual_mode=False, max_pages=None, max_articles=50, headless=False, progress_callback=None):
    """
    同步接口，用於在非異步環境中調用爬蟲

    Args:
        參數同 run_scraper

    Returns:
        DataFrame: 包含爬取的新聞資料的 Pandas DataFrame
    """
    import nest_asyncio
    nest_asyncio.apply()  # 啟用嵌套事件循環支持
    
    return asyncio.get_event_loop().run_until_complete(run_scraper(
        keyword=keyword,
        start_date=start_date,
        end_date=end_date,
        output_file=output_file,
        manual_mode=manual_mode,
        max_pages=max_pages,
        max_articles=max_articles,
        headless=headless,
        progress_callback=progress_callback
    ))