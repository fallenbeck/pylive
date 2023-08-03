#!/usr/bin/env python3
import datetime
import locale
import logging
import markdown
import os
import re
import pprint
import sys
import threading
from contextlib import contextmanager
from jinja2 import Environment, FileSystemLoader
from slugify import slugify

# Settings for this script. Should be parametrized later.
POSTSDIR = "blogs/cno/posts"
OUTPUTDIR = "blogs/cno/out"
TEMPLATEDIR = "blogs/cno/templates"
DEFAULT_LOCALE = "de_DE"

# Output format
# the "-" in %-d will remove the leading 0 (if any)
FMT_DATE_OUTPUT = "%A, %-d. %B %Y"

IGNOREFILES = ["README", "TEMPLATE"]  # , "helloworld"]
EXTENSIONS = [".md"]

# Set up logging
log_formatter = logging.Formatter('%(message)s')
# DEFAULT_LOGLEVEL = logging.WARNING
DEFAULT_LOGLEVEL = logging.DEBUG
log = logging.getLogger()
log.setLevel(DEFAULT_LOGLEVEL)

# Set locale to de_DE to get german output (day of week, ...)
locale.setlocale(locale.LC_ALL, "de_DE")


class Post:
    """This object represents a post.

    A post object does not only contain the post's contents (text) but does
    also have some meta information such as the title, the post's publish date
    and the post's author (and maybe others).

    Each post is represented as a markdown file in the file system.
    """

    # Full path to source file name (Markdown file of post)
    filename: str = ""

    # Name of the (output) file
    # Will be derived from the input filename
    # slug: str = ""

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

    # The following attributes will be set by self.__parse_attributes

    # The the post's language (locale)
    # Can be derived from the blog's default language (if not set in post)
    # or set individually using the "lang" or "language" attribute
    lang: str = DEFAULT_LOCALE

    # Date and time of publication
    # Must be set by "date" keyword in post's heade
    date: datetime.datetime = None

    # Human-readable string representing the date, i.e.
    # "Donnerstag, 3. August 2023"
    printable_date: str = ""

    # If post is a draft
    # This literally means that this script ignores this post
    draft: bool = False

    # If post has a valid header section and can be published
    # Set by self.__validate_header()
    valid: bool = True

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

        # Set additional attributes
        self.__parse_attributes(self.meta)

    # Define properties ("getters") to get daata from the meta dictionary.
    # If a specified property does not exist in the dictionary the getter
    # functions must return a meaninungful value.

    @property
    def title(self) -> str:
        return self.meta.get("title", "Untitled")

    # @property
    # def date(self) -> str:
    #     return "Heute"

    @property
    def basename(self) -> str:
        return os.path.basename(self.filename)

    @property
    def slug(self) -> str:
        return slugify(os.path.splitext(self.basename)[0])

    @property
    def html(self) -> str:
        return self.rendered_text

    # @property
    # def draft(self) -> bool:
    #     return "draft" in self.meta.keys()

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
            result[key.lower().strip()] = value.strip()

        log.info(f"Found {len(result)} meta key(s): {list(result.keys())}")
        log.debug(pprint.pformat(result))

        # Validate header
        if not self.__validate_header(result):
            self.valid = False
            raise Exception(f"Invalid/insufficient header/preamble in "
                            f"{self.filename}")
        else:
            self.valid = True

        return result

    def __validate_header(self,
                          header: dict[str, str],
                          required_keys: list[str] = ["title", "date"],
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

        missing_keys = set(required_keys) - set(header.keys())
        if len(missing_keys) > 0:
            log.error(f"Invalid header! Missing keys: {missing_keys}")
            self.valid = False

        # Check if date is in a known format that can be parsed
        if "date" in header.keys():
            self.date = self.__parse_date(header["date"])
            if not self.date:
                self.valid = False

        return True

    def __parse_attributes(self,
                           meta: dict[str, str]):
        """

        """
        log.info("Parse attributes from post header/preamble")
        # language
        for lang_key in ["lang", "language"]:
            if lang_key in meta.keys():
                self.lang = meta[lang_key].strip()
                log.info(f"Set language to {self.lang}")
                break

        # date
        self.date == self.__parse_date(meta["date"])
        if self.date:
            self.printable_date = self.__create_printable_date(self.date,
                                                               self.lang)

        # draft
        self.draft = ("draft" in meta.keys())
        if self.draft:
            log.debug("Mark as draft")

    def __parse_date(self,
                     prefix_date: str) -> datetime.datetime:
        """
        """
        log.debug(f"Create printable date from {prefix_date}")

        # Supported input formats
        supported_formats: list[str] = [
                "%d.%m.%y",     # 01.01.23
                "%d.%m.%Y",     # 01.01.2023
                ]

        dt: datetime.datetime = None

        for fmt in supported_formats:
            try:
                dt = datetime.datetime.strptime(prefix_date, fmt)
            except Exception as e:
                # log.warning(f"Could not parse {fmt}: {e}")
                continue

            break

        if dt:
            log.info(f"Parsed date: {dt}")
            return dt
        else:
            log.error(f"Invalid date format: {prefix_date}")

        return None

    LOCALE_LOCK = threading.Lock()

    @contextmanager
    def setlocale(self, name):
        with self.LOCALE_LOCK:
            saved = locale.setlocale(locale.LC_ALL)
            try:
                yield locale.setlocale(locale.LC_ALL, name)
            finally:
                locale.setlocale(locale.LC_ALL, saved)

    def __create_printable_date(self,
                                date: datetime.datetime,
                                locale: str = None) -> str:
        """

        """
        result: str = None
        if locale:
            try:
                with (self.setlocale(locale)):
                    result = date.strftime(FMT_DATE_OUTPUT)
            except Exception as e:
                log.warning(f"Could not create printable date in {self.lang}: {e}")

        if not result:
            result = date.strftime(FMT_DATE_OUTPUT)

        log.info(f"Created from {date}: {result}")
        return result

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
        if self.date:
            shortdate = datetime.datetime.strftime(self.date, "%d.%m.%Y")
        else:
            shortdate = "UNSET_DATE"
        return f"{shortdate} {self.title} ({self.filename} -> {self.slug})"

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
            log.setLevel(DEFAULT_LOGLEVEL)

        if not os.path.isdir(POSTSDIR):
            log.error(f"{POSTSDIR} is not a directory!")
            sys.exit(1)
        self.posts_directory = POSTSDIR

        self.main()

    def list_post_files_to_compile(
            self,
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
        log.info(f"Search for post files in \"{path}\"")
        log.debug(f"Valid file extensions: {extensions}")
        log.debug(f"Filenames to ignore: {ignore}")
        files = [f for f in os.listdir(path)
                 if os.path.isfile(os.path.join(path, f))
                 and os.path.splitext(f)[1] in extensions
                 and os.path.splitext(f)[0] not in ignore
                 ]
        log.info(f"{len(files)} post files found: {files}")
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
                   post: Post):
        """Write post as HTML file to specific file.

        :param post:        Post to write
        :type post:         Post
        :param output_file: Target file to write (in HTML format)
        :type output_file:  str
        """
        log.debug(f"Write {post} to {post.slug}")

    def get_list_of_posts(self,
                          path: str,
                          extensions: list[str],
                          ignore_files: list[str],
                          ) -> list[Post]:
        """Return list of post objects to be published sorted by the posts'
        publication date from newest to oldest (newest post is the first element
                                                in the list).
        """
        # Will hold the post objects
        # result: list[Post] = []
        list_of_post_objects: list[Post] = []

        log.debug(f"Scan {path} for files with extensions {extensions}, "
                  f"ignoring {ignore_files}")
        post_files_to_compile = self.list_post_files_to_compile(
                path=path,
                extensions=extensions,
                ignore=ignore_files,
                )

        for post_file in post_files_to_compile:
            post = self.create_post_object(path=self.posts_directory,
                                           filename=post_file)

            # Ignore post objects that are None or marked as draft
            # (when an error has occurred during Post object creation, e.g.
            #  because of missing header/preamble)
            if post and not post.draft:
                log.debug(f"Add {post} to list of posts to compile")
                list_of_post_objects.append(post)

        log.warning(f"{len(list_of_post_objects)} post objects created")

        log.debug("Sort list of posts to publish by date")
        list_of_post_objects = sorted(list_of_post_objects,
                                      key=lambda p: p.date,
                                      reverse=True)

        return list_of_post_objects

    def write_index(self,
                    post: Post,
                    template_file: str,
                    output_file: str,
                    ):
        """

        """


    def write_post_file(self,
                        post: Post,
                        output_directory: str):
        """Write post as HTML file to specific file.

        :param post:        Post to write
        :type post:         Post
        :param output_file: Target file to write (in HTML format)
        :type output_file:  str
        """
        log.debug(f"Write {post} to {post.slug}")

    def main(self) -> None:
        """This is the main function that coordinates the run."""
        list_of_posts_to_compile = self.get_list_of_posts(
                path=self.posts_directory,
                extensions=self.post_extensions,
                ignore_files=self.ignore_filenames,
                )

        log.warning(pprint.pformat(list_of_posts_to_compile))


if __name__ == '__main__':
    pyl = PyLive()
