import asyncio
import json
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

SBR_WS_CDP = 'wss://{username}:{password}@brd.superproxy.io:9222'


async def connect_to_browser(playwright):
    print('Connecting to Scraping Browser...')
    browser = await playwright.chromium.connect_over_cdp(SBR_WS_CDP)
    return browser


async def navigate_to_page(page, url):
    print(f'Navigating to {url}...')
    await page.goto(url)


async def handle_captcha(page):
    client = await page.context.new_cdp_session(page)
    print('Waiting for CAPTCHA to be solved...')
    solve_res = await client.send('Captcha.waitForSolve', {
        'detectTimeout': 10000,
    })
    print('CAPTCHA solve status:', solve_res['status'])


async def scroll_and_load_results(page):
    print('Scrolling and loading more results...')
    num_relevant_results = 0

    while num_relevant_results < 40:
        await page.evaluate('''
            async () => {
                await new Promise((resolve) => {
                    let totalHeight = 0;
                    const distance = 100;
                    const timer = setInterval(() => {
                        const scrollHeight = document.body.scrollHeight;
                        window.scrollBy(0, distance);
                        totalHeight += distance;
                        if (totalHeight >= scrollHeight) {
                            clearInterval(timer);
                            resolve();
                        }
                    }, 100);
                });
            }
        ''')
        await page.wait_for_timeout(2000)  # Wait for new results to load
        num_relevant_results = await page.evaluate('''
            () => {
                const placeCards = document.querySelectorAll('a[href^="https://www.skyscanner.co.in/transport/flights/"]');
                return placeCards.length;
            }
        ''')
        print(f'Loaded {num_relevant_results} relevant results so far...')


async def scrape_page_content(page):
    print('Scraping page content...')
    html = await page.content()
    return html


def parse_html(html):
    soup = BeautifulSoup(html, 'html.parser')
    place_cards = soup.find_all('a', href=lambda href: href and href.startswith('https://www.skyscanner.co.in/transport/flights/'))
    data = []

    for card in place_cards:
        try:
            link = card['href']
            destination_elem = card.find('div', class_=lambda x: x and 'nameContainer' in x)
            destination = destination_elem.get_text(strip=True) if destination_elem else 'N/A'
            price_elem = card.find('div', class_=lambda x: x and 'priceContainer' in x)
            price = price_elem.get_text(strip=True) if price_elem else 'N/A'

            item = {
                'link': link,
                'destination': destination,
                'price': price
            }
            data.append(item)
        except AttributeError:
            continue

    return data


def save_data_to_json(data, filename):
    with open(filename, 'w') as f:
        json.dump(data, f, indent=4)
    print(f"Data extracted and saved as {filename}")


async def run(playwright, url):
    browser = await connect_to_browser(playwright)
    try:
        page = await browser.new_page()
        await navigate_to_page(page, url)
        # await handle_captcha(page)  # Uncomment if CAPTCHA handling is needed
        await scroll_and_load_results(page)
        html = await scrape_page_content(page)
        data = parse_html(html)
        save_data_to_json(data, 'skyscanner_results.json')
    finally:
        await browser.close()


async def main():
    url = "'https://www.skyscanner.co.in/transport/flights-from/in/?adultsv2=1&cabinclass=economy&childrenv2=&ref=home&rtn=0&preferdirects=true&outboundaltsenabled=false&inboundaltsenabled=false&oym=2404'"
    async with async_playwright() as playwright:
        await run(playwright, url)


if __name__ == '__main__':
    asyncio.run(main())