import selenium.webdriver as webdriver
import pandas as pd
from bs4 import BeautifulSoup
from IPython.display import Image
import os
import time
import requests
import re


class InstagramDownloader:
    def __init__(self, dir_path, mksubdir=True, browser=None, timeout=1, max_posts=100):
        """
        Class the downloads the public content of a targeted profile

        Inputs:
        dir_path  -> str, home dir of the project
        mksubdir  -> bool, set to True to save the media of each profile
                     on a subdir within the home dir of the project
        browser   -> instance of selenium.webdriver.Firefox(), with the
                     addon instagram-guest installed
        timeout   -> int, seconds between each scrolling done by the browser
                     (scrolls are done to load more posts)
        max_posts -> int, max number of posts gathered per profile
        """
        self.dir_path = dir_path
        self.mksubdir = mksubdir
        self.browser = self.get_browser() if browser is None else browser
        self.timeout = timeout
        self.max_posts = max_posts

        # Ensure dir of project exists
        if not os.path.exists(self.dir_path):
            os.mkdir(self.dir_path)

        # Load project's .csv file, or create new Pandas Df where the lines and titles
        # of each post will be saved
        try:
            self.df_stats = pd.read_csv(
                os.path.join(self.dir_path, 'stats.csv'))
        except:
            self.df_stats = pd.DataFrame(columns=['path', 'likes', 'title'])

    def download_profile(self, profile):
        """
        Main method. Downloads all the posts in the profile (or up to limits defined in
        the initialisation of the function). It also updates the df_stats and the .csv
        so that we know the like and title of each post
        """
        if self.mksubdir:
            if not os.path.exists(os.path.join(self.dir_path, profile)):
                os.mkdir(os.path.join(self.dir_path, profile))
            path = os.path.join(profile, profile)
        else:
            path = profile
        post_urls = self.get_post_urls(profile)
        c = 0
        for url in post_urls:
            self.download_post(url, path + '_' + str(c))
            c += 1
        self.save_stats()

    def get_post_urls(self, profile):
        """Gets the urls of all the posts in the profile"""
        self.browser.get('https://www.instagram.com/' + profile)
        self.browser.set_window_size(300, 1000)
        post_urls = []
        profile_end = False
        nr_posts = 0
        while len(post_urls) < self.max_posts and not profile_end:
            # Get scroll height
            last_height = self.browser.execute_script(
                'return document.body.scrollHeight')
            # Get all URL's of all posts currently loaded
            soup = BeautifulSoup(self.browser.page_source, features="lxml")
            all_as = soup.find_all('a', href=True)
            for a in all_as:
                if a['href'][:3] == '/p/' and a['href'] not in post_urls:
                    post_urls.append(a['href'])
                    nr_posts += 1
                    if nr_posts >= self.max_posts:
                        break
            # Scroll down to bottom and wait to load page
            self.browser.execute_script(
                'window.scrollTo(0, document.body.scrollHeight);')
            time.sleep(self.timeout)
            # Calculate new scroll height and compare with last scroll height
            new_height = self.browser.execute_script(
                'return document.body.scrollHeight')
            if new_height == last_height:
                profile_end = True
            else:
                last_height = new_height

        return ['https://www.instagram.com' + a for a in post_urls]

    def download_post(self, url, path):
        """
        Function to download an instagram photo or video

        Inputs:
        url  -> str with url of the post to download
        path -> str with relative (to project's directory) path of the file,
                do not include .jpg or .mp4 extension, since this will be
                based on the file
        """
        request_image = requests.get(url)
        src = request_image.content.decode('utf-8')
        # Get type of content, i.e. img or video
        check_type = re.search(
            r'<meta name="medium" content=[\'"]?([^\'" >]+)', src)
        check_type_f = check_type.group()
        the_type = re.sub('<meta name="medium" content="', '', check_type_f)
        try:
            # Get likes
            check_type = re.search(r'<meta content=[\'"]?([^\'" >]+)', src)
            check_type_f = check_type.group()
            likes = re.sub('<meta content="', '', check_type_f)
            if 'm' in likes:
                likes = int(float(likes.replace('m', ''))*(10**6))
            elif 'k' in likes:
                likes = int(float(likes.replace('k', ''))*(10**3))
            else:
                likes = int(likes)
            # Get title
            title = BeautifulSoup(src, features="lxml").find_all(
                'title')[0].get_text().replace('\n', '')
        except:
            likes, title, the_type = None, None, None

        if the_type == 'image':
            extract_image_link = re.search(
                r'meta property="og:image" content=[\'"]?([^\'" >]+)', src)
            image_link = extract_image_link.group()
            final = re.sub(
                'meta property="og:image" content="', '', image_link)
            _response = requests.get(final).content
            file_size_request = requests.get(final, stream=True)
            block_size = 1024
            with open(os.path.join(self.dir_path, path) + '.jpg', 'wb') as f:
                for data in file_size_request.iter_content(block_size):
                    f.write(data)
            idx = self.df_stats.index[-1] + \
                1 if len(self.df_stats.index) != 0 else 0
            self.df_stats.loc[idx, 'path'] = path + '.jpg'
            self.df_stats.loc[idx, 'likes'] = likes
            self.df_stats.loc[idx, 'title'] = title

        if the_type == 'video':
            extract_video_link = re.search(
                r'meta property="og:video" content=[\'"]?([^\'" >]+)', src)
            video_link = extract_video_link.group()
            final = re.sub(
                'meta property="og:video" content="', '', video_link)
            _response = requests.get(final).content
            file_size_request = requests.get(final, stream=True)
            block_size = 1024
            with open(os.path.join(self.dir_path, path) + '.mp4', 'wb') as f:
                for data in file_size_request.iter_content(block_size):
                    f.write(data)
            idx = self.df_stats.index[-1] + \
                1 if len(self.df_stats.index) != 0 else 0
            self.df_stats.loc[idx, 'path'] = path + '.mp4'
            self.df_stats.loc[idx, 'likes'] = likes
            self.df_stats.loc[idx, 'title'] = title

    def get_browser(self):
        """
        Returns a selenium.webdriver.Firefox() instance with the addon
        instagram-guest loaded. You need to have Firefox installed
        together with the addon.

        !!! Note that the path is only valid for Mac

        Get addon from: https://addons.mozilla.org/en-US/firefox/addon/instagram-guest/
        """
        addon_dir = os.path.join(os.path.expanduser('~'), 'Library', 'Application Support',
                                 'Firefox', 'Profiles', 'vqkmeiit.default', 'extensions')
        addon = '{8e6822de-d72f-4284-9400-1164ee39b07d}.xpi'
        browser = webdriver.Firefox()
        browser.install_addon(os.path.join(addon_dir, addon), temporary=True)

        return browser

    def save_stats(self):
        """convenience call to save df_stats to .csv"""
        self.df_stats.to_csv(os.path.join(
            self.dir_path, 'stats.csv'), index=False)

    def show_img(self, path):
        Image(filename=os.path.join(indo.dir_path, path))

    def show_top_img(self):
        path = self.df_stats.loc[self.df_stats['likes'].astype(
            int).idxmax(), 'path']
        Image(filename=os.path.join(self.dir_path, path))


if __name__ == '__main__':

    # Scrap the Instagram Profile of comedians Joe Rogan and Bert Kreischer
    BASE_DIR = os.path.dirname(os.path.abspath(__file__))
    indo = InstagramDownloader(
        dir_path=os.path.join(BASE_DIR, 'imgs_stats'), max_posts=5)
    indo.download_profile('joerogan')
    indo.download_profile('bertkreischer')
