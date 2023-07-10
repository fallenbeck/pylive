#!/usr/bin/env python3

import logging
import markdown
import os
import pprint
import sys

# Settings for this script. Should be parametrized later.
POSTSDIR = "posts"
OUTPUTDIR = "out"
TEMPLATEDIR = "templates/cno"

IGNOREFILES = ["README", "TEMPLATE"]  # , "helloworld"]
EXTENSIONS = [".md"]

# Set up logging
log_formatter = logging.Formatter('%(message)s')
DEFAULT_LOGLEVEL = logging.WARNING
log = logging.getLogger()
log.setLevel(DEFAULT_LOGLEVEL)


class PyLive:

    # Path where the posts (in Markdown format) are stored
    posts_directory: str = ""

    ignore_filenames: list[str] = IGNOREFILES
    post_extensions: list[str] = EXTENSIONS

    def __init__(self):
        """Initialize pylive.

        This function sets the variables needed to run script.
        """
        # Initialize the logging facility and add a handler if none is present
        global log
        if len(log.handlers) == 0:
            stdout = logging.StreamHandler()
            stdout.setFormatter(log_formatter)
            log.addHandler(stdout)
            # log.setLevel(DEFAULT_LOGLEVEL)
            log.setLevel(logging.DEBUG)

        log.warning("Hello, world.")

        if not os.path.isdir(POSTSDIR):
            log.error(f"{POSTSDIR} is not a directory!")
            sys.exit(1)
        self.posts_directory = POSTSDIR

        self.main()

    def list_posts_to_compile(self,
                              path: str,
                              extensions: list[str] = [".md", ".markdown"],
                              ignore: list[str] = ["README", "TEMPLATE"],
                              ) -> list[str]:
        """Return the list of post names to be compiled.

        This function will return a list of files existing in the post's
        directory. Files in subdirectories will not displayed.

        The returned list will only contain files with a file extensions listed
        in extensions. The string elements need to start with "." because
        Python's os.path.splitext() function returns the file extension of a
        file with a leading ".".
        By default Markdown files with .md and .markdown extensions are
        returned by this function.

        The ignore list contains file names (without extension) that are
        ignored. By default, README and TEMPLATE files will not be returned by
        this function.

        :param path:        Path where blog posts to compile are stored
        :type path:         str
        :param extensions:  List of valid extenions of the files to be returned
        :type extensions:   list[str]
        :param ignore:      List of file names to ignore (without extension)
        :type ignore:       list[str]
        :return:            List of file names to be compiled
        :rtype:             list[str]
        """
        log.info(f"Return list of posts to compile in \"{path}\"")
        log.debug(f"Valid file extensions: {extensions}")
        log.debug(f"Filenames to ignore: {ignore}")
        files = [f for f in os.listdir(path)
                 if os.path.isfile(os.path.join(path, f))
                 and os.path.splitext(f)[1] in extensions
                 and os.path.splitext(f)[0] not in ignore
                 ]
        log.debug(f"Return list with {len(files)} post files: {files}")
        return files

    def render(self,
               path: str,
               filename: str,
               ) -> str:
        """Render the contents of the given file to HTML.

        :param path:        Path where blog posts to compile are stored
        :type path:         str
        :param filename:    Name of the file to render
        :type filename:     str
        :return:            Rendered HTML content
        :rtype:             str
        """
        full_filename = os.path.join(path, filename)
        log.info(f"Rendering {full_filename}")
        with open(full_filename, 'r') as f:
            text = f.read()
            # log.debug(f"Markdown:\n{text}")

            html = markdown.markdown(text)
            # log.debug(f"HTML:\n{html}")

        return html

    def rendered_list(self,
                      path: str,
                      files: list[str],
                      ) -> list[dict[str, str]]:
        """Return a list that contains the dicts of the blog posts
        with rendered HTML and other data for each post.

        Each dict - representing a blog post - contains the following keys:
            html    Rendered HTML
            file    Filename of the markdown file
            title   Title of the post
            date    Date for the post
            author  Author(s) of the post
            tags    Tags

        The list of dicts is sorted by the date with the most recent post
        at the beginning of the list.

        :param path:    Base path of the files containing the posts
        :type path:     str
        :param files:   Files of the posts to render
        :type files:    list[str]
        :return:        List of dictionaries with metadata and HTML
        :rtype:         list[dict[str, str]]
        """
        list_of_posts: list[dict[str, str]] = []

        for filename in files:
            html = self.render(path=path,
                               filename=filename,
                               )
            post: dict[str, str] = {}
            post["html"] = html
            post["file"] = filename
            list_of_posts.append(post)

        log.debug(f"Return list with {len(list_of_posts)} posts")
        return list_of_posts

    def main(self) -> None:
        """This is the main function that coordinates the run."""
        posts = self.list_posts_to_compile(
                path=self.posts_directory,
                extensions=self.post_extensions,
                ignore=self.ignore_filenames,
                )
        log.warning(f"Posts to compile: {posts}")

        for post in posts:
            log.debug(self.render(path=self.posts_directory,
                                  filename=post))

        rendered_posts = self.rendered_list(path=self.posts_directory,
                                            files=posts,
                                            )
        log.debug(pprint.pformat(rendered_posts))


if __name__ == '__main__':
    pyl = PyLive()
