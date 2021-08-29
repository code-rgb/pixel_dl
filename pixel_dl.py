import argparse
import asyncio

import re
import sys
from typing import List, Optional, Pattern
import traceback
import pyppeteer
from aiohttp import ClientSession, ClientTimeout


class Constants:
    rom_regex: Pattern = re.compile(
        r"https://download\.pixelexperience\.org/changelog/(\w+/[\w.-]+\.zip)"
    )
    rom_url: str = "https://download.pixelexperience.org/changelog/"
    useragent: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/74.0.3729.157 Safari/537.36"
    )
    browser_args: List[str] = [
        "--no-sandbox",
        "--disable-accelerated-2d-canvas",
        "--disable-gpu",
    ]
    button: str = (
        "body > main > div.device__info.wrap > div.device__downloads "
        "> div > div.accordion_tab.version__item.item__expanded > div > div >"
        " div.package__data > div.accordion_tab.build__item.item__expanded >"
        " div > div.build__ddata > div > a:nth-child(1)"
    )
    a_tag: str = "#swal2-content > a"
    href: str = """
    element => {  
        return element.href;    
    }"""


async def fetch_rom(
    url: str,
    browser: pyppeteer.browser.Browser,
    sem: asyncio.Semaphore,
    session: ClientSession,
) -> Optional[str]:
    """[Fetch direct link from single link]

    Args:
        url (str): [A pixel experience rom link]
        browser (pyppeteer.browser.Browser): [Browser instance]
        sem (asyncio.Semaphore): [Max Parallel process]
        session (ClientSession): [Http Session]

    Returns:
        Optional[str]: [Direct link]
    """
    async with sem:
        page = await browser.newPage()
        await page.setUserAgent(Constants.useragent)
        if not url.startswith("http:"):
            url = Constants.rom_url + url
        print(f"---->  Fetching {url}")
        await page.goto(url)
        rom_button = await page.waitForSelector(Constants.button)
        await rom_button.click()
        element = await page.waitForSelector(Constants.a_tag)
        dl_link = await page.evaluate(Constants.href, element)
        await page.close()
        async with session.get(dl_link, timeout=ClientTimeout(total=30)) as resp:
            if resp.status == 200:
                print("       SUCCESS")
                return str(resp.url)
            print(f"       Failed to get [{url}] => Status Code: ({resp.status})")


async def start(url_list: List[str]) -> None:
    """[Provide Url(s) to write direct links to 'direct_link.txt']

    Args:
        url_list (List[str]): [ Url(s) ]
    """
    print(f"Detected {len(url_list)} URL(s), processing ...")
    sem = asyncio.Semaphore(5)
    session = ClientSession(headers={"User-Agent": Constants.useragent})
    browser = await pyppeteer.launch(headless=True, args=Constants.browser_args)
    try:
        direct_links = await asyncio.gather(
            *map(lambda x: fetch_rom(x, browser, sem, session), url_list)
        )
    except Exception:
        traceback.print_exc()
        direct_links = None
    finally:
        if session and not session.closed:
            await session.close()
        await browser.close()
    if direct_links and (data := "\n".join(filter(None, direct_links))):
        print("---->  Writing to links to 'direct_link.txt'")
        with open("direct_link.txt", "w") as outfile:
            outfile.write(data)


def rom_link_type(arg_value: str) -> str:
    """[Type checker of command line]

    Args:
        arg_value (str): [Url]

    Raises:
        argparse.ArgumentTypeError: [In case of invalid Url]

    Returns:
        str: [device/rom.zip]
    """
    if not (match := Constants.rom_regex.match(arg_value)):
        raise argparse.ArgumentTypeError(f"Must match {Constants.rom_regex.pattern}")
    return match.group(1)


def main() -> None:
    """[main function]"""
    parser = argparse.ArgumentParser(
        description="Give URL(s) to get direct download link"
    )
    parser.add_argument(
        "url", help="Pixel Experience Rom URL", type=rom_link_type, nargs="+"
    )
    args = parser.parse_args()
    if sys.platform == "win32":
        asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(start(args.url))
            loop.run_until_complete(asyncio.sleep(1))
        finally:
            loop.close()
    else:
        try:
            import uvloop
        except ImportError:
            policy = asyncio.DefaultEventLoopPolicy()
        else:
            policy = uvloop.EventLoopPolicy()
        asyncio.set_event_loop_policy(policy)
        asyncio.run(start(args.url))


if __name__ == "__main__":
    main()
