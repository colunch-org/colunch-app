from pathlib import Path

from config import Config


CONFIG = Config()


class Html:
    def __init__(self, html_dir: Path | None = None) -> None:
        html_dir = CONFIG.html_dir if html_dir is None else html_dir

        with open(html_dir / "index.html") as f:
            self.index = f.read()

        with open(html_dir / "preferences.html") as f:
            self.preferences = f.read()

        with open(html_dir / "recipe-method.html") as f:
            self.recipe_method = f.read()

        with open(html_dir / "empty-recipe-method.html") as f:
            self.empty_recipe_method = f.read()

        with open(html_dir / "youtube-url-div.html") as f:
            self.youtube_url_form = f.read()

        with open(html_dir / "empty-youtube-url-div.html") as f:
            self.empty_youtube_url_form = f.read()

        with open(html_dir / "youtube-url-ws.html") as f:
            self.youtube_url_ws = f.read()

        with open(html_dir / "webpage-url-div.html") as f:
            self.webpage_url_form = f.read()

        with open(html_dir / "empty-webpage-url-div.html") as f:
            self.empty_webpage_url_form = f.read()

        with open(html_dir / "webpage-url-ws.html") as f:
            self.webpage_url_ws = f.read()

        with open(html_dir / "images-div.html") as f:
            self.images_form = f.read()

        with open(html_dir / "empty-images-div.html") as f:
            self.empty_images_form = f.read()

        with open(html_dir / "images-ws.html") as f:
            self.images_ws = f.read()
