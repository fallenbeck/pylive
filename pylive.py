#!/usr/bin/env python3
import datetime
import logging
import markdown
import os
import re
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

class Post:
    """This object represents a post.

    A post object does not only contain the post's contents (text) but does also
    chave some meta information such as the title, the post's publish date and
    the post's author (and maybe others).

    Each post is represented as a markdown file in the file system.
    """

    # Full path to source file name (Markdown file of post)
    filename: str = ""

    # Keep the contents of the file in this variable.
    # This contains the original contents used to parse the Post object
    raw: str = ""

    # Raw markdown text of post without header/preamble
    # (textblock surrounded by '---\n')
    raw_text: str = ""

    # HTML code of the post as provided in the markdown file/raw variable
    # without the header/preamble block (text surrounded by '---\n')
    rendered_text: str = ""

    # The meta dictionary contains all information described in the post's
    # preamble as a key-value pair.
    meta: dict[str, str] = {}

    def __init__(self,
                 full_filename: str):
        """The initialization function awaits the markdown text of this blog
        post. This text will be parsed to get the meta information as well as
        the post's text.

        :param full_filename:   full path to Markdown filename of post
        :type full_filename:    str
        """
        log.info(f"Create post object from {full_filename}")
        self.filename = full_filename
        self.raw = self.__read_file(self.filename)
        self.meta, self.raw_text = self.__segment(self.raw)
        self.rendered_text = self.__render(self.raw_text)

    # Define properties ("getters") to get daata from the meta dictionary.
    # If a specified property does not exist in the dictionary the getter
    # functions must return a meaninungful value.

    @property
    def title(self) -> str:
        return self.meta.get("title", "Untitled")

    @property
    def date(self) -> str:
        return "Heute"

    @property
    def html(self) -> str:
        return self.rendered_text

    @property
    def valid(self) -> bool:
        return self.__validate_header(self.meta)

    @property
    def draft(self) -> bool:
        return "draft" in self.meta.keys()

    def __read_file(self,
                    full_filename: str) -> str:
        """Read the contents from the specified file.

        :param full_filename:   Full path to (Markdown) file to read
        :type full_filename:    str
        :return:                Contents of the file
        :rtype:                 str
        """
        log.info(f"Read {full_filename}")
        with open(full_filename, 'r') as f:
            text = f.read()
        return text

    def __segment(self,
                  text: str) -> tuple[dict[str, str], str]:
        """Parse the raw text of the post and segment it into 2 elements.
        Return a 2-tuple containing the metadata dict as first element and the
        posts raw markdown text (without the header/preamble of the post) as
        second element.

        First element:  Header/Preamble     dict[str,str]
        Second element: Raw Markdown text   str

        :param text:    Complete text of Markdown file for post
        :type text:     str
        :return:        Metadata dictionary and raw markdown text
        :rtype:         (dict(str, str), str)
        """
        # Split self.raw into segments (separated by ---)
        pattern = r"---\s*\n"

        # Remove empty segments and strip() leading and trailing whitespaces
        segments = [s.strip() for s in re.split(pattern, text)
                    if len(s.strip()) > 0]

        log.debug(f"Regex split, {len(segments)} segments")
        # if log.level == logging.DEBUG:
        #     snr = 0
        #     for segment in segments:
        #         snr += 1
        #         log.debug(f"[{snr}] {segment}")

        # The markdown text is contained in the last segment
        # The meta information is contained in the second last segment
        # We use relative positioning form the last element because we do not
        # know if we get 2 or 3 segments: if the preable is between ---'s we
        # get 3 segments, if only the closing --- is present we get 2 segments
        if len(segments) < 2:
            msg = f"Could not find header/preamble segment in {self.filename}"
            log.error(msg)
            raise Exception(msg)

        # Prse the meta information from the header/preamble
        meta_dict: dict[str, str] = self.__parse_header(segments[-2])
        raw_text = segments[-1]
        return (meta_dict, raw_text)

    def __parse_header(self,
                       header: str) -> dict[str, str]:
        """Parse raw Markdown text and return the contents of the header as
        dictionary.

        The string expeced by this function can have multiple lines separated
        by newlines and looks as follows
        >---<
        title: "Techniker ist informiert!"
        date: 27.07.2023
        author: "Niels"
        >---<

        :param header:  Header segment
        :type header:   str
        :return:        Key-value-pairs of header/preample entries
        :rtype:         dict
        """
        log.info("Parse header/preamble section")
        log.debug(header)

        result: dict[str, str] = {}
        for line in header.splitlines():
            key, value = line.split(":", 1)
            # Keys will be stored in lowercase
            result[key.lower()] = value

        log.info(f"Found {len(result)} meta key(s): {list(result.keys())}")
        log.debug(pprint.pformat(result))

        if not self.__validate_header(result):
            raise Exception(f"Invalid/insufficient header/preamble in "
                            f"{self.filename}")

        return result

    def __validate_header(self,
                          header: dict[str, str],
                          required_keys: list[str] = ["title", "date"],
                          valid_if_draft: bool = True,
                          ) -> bool:
        """Validate header/preamble information.

        :param header:          Dict containing header/preamble data
        :type header:           dict[str, str]
        :param required_keys:   Keys that must be contained in header dict
        :type required_keys:    list[str]
        :param valid_if_draft:  Skip header verification if key "draft" exists
        :type valid_if_draft:   bool
        :return:                Whether or not header is valid
        :rtype:                 bool
        """
        log.info(f"Validate header of {self}")
        result = True

        missing_keys = set(required_keys) - set(header.keys())
        if len(missing_keys) > 0:
            log.error(f"Invalid header! Missing keys: {missing_keys}")
            result = False

        return result or (valid_if_draft and "draft" in header.keys())



    def __render(self,
                 text: str) -> str:
        """Render the text of the post into HTML.
        Result is stored in self.hmtl variable

        :param text:    Post's text in Markdown format
        :type text:     str
        :return:        Text of post converted to HTML
        :rtype:         str
        """
        log.info("Convert Markdown to html")
        # log.debug(text)
        html = markdown.markdown(text)
        # log.debug(html)
        return html

    def __str__(self):
        return f"{self.title} ({self.filename})"

    def __repr__(self):
        return str(self)


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
            log.setLevel(logging.INFO)

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
        log.info(f"Search for posts to compile in \"{path}\"")
        log.debug(f"Valid file extensions: {extensions}")
        log.debug(f"Filenames to ignore: {ignore}")
        files = [f for f in os.listdir(path)
                 if os.path.isfile(os.path.join(path, f))
                 and os.path.splitext(f)[1] in extensions
                 and os.path.splitext(f)[0] not in ignore
                 ]
        log.info(f"{len(files)} posts to compile: {files}")
        return files

    def create_post_object(self,
                           path: str,
                           filename: str) -> Post | None:
        """Create a Post object for a particular post.

        :param path:        Path where blog posts to compile are stored
        :type path:         str
        :param filename:    Name of the file to render
        :type filename:     str
        :return:            Object representing the post
        :rtype:             Post | None
        """
        full_filename = os.path.join(path, filename)
        try:
            post = Post(full_filename)
            return post
        except Exception as e:
            log.error(f"Could not create Post: {e}")

    def write_posts(self,
                    list_of_posts: list[Post],
                    output_dir: str):
        """Write the list of Posts as files to the specified output directory.

        :param list_of_posts:   List of posts to write
        :type list_of_posts:    list[Post]
        :param output_dir:      Target directory to put output files to
        :type output_dir:       str
        """
        log.info(f"Write {len(list_of_posts)} output files to {output_dir}")
        for post in list_of_posts:
            self.write_post(post, "lala.html")

    def write_post(self,
                   post: Post,
                   output_file: str):
        """Write post as HTML file to specific file.

        :param post:        Post to write
        :type post:         Post
        :param output_file: Target file to write (in HTML format)
        :type output_file:  str
        """
        log.debug(f"Write {post}")

    def main(self) -> None:
        """This is the main function that coordinates the run."""
        posts_to_compile = self.list_posts_to_compile(
                path=self.posts_directory,
                extensions=self.post_extensions,
                ignore=self.ignore_filenames,
                )

        list_of_post_objects: list[Post] = []
        for post_file in posts_to_compile:
            post = self.create_post_object(path=self.posts_directory,
                                           filename=post_file)

            # Ignore post objects that are None
            # (when an error has occurred during Post object creation, e.g.
            #  because of missing header/preamble)
            if post:
                list_of_post_objects.append(post)

        log.warning(f"{len(list_of_post_objects)} post objects created")
        log.warning(pprint.pformat(list_of_post_objects))


if __name__ == '__main__':
    pyl = PyLive()
