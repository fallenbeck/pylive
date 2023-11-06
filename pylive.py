#!/usr/bin/env python3
from __future__ import annotations
from datetime import datetime
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
from slugify import UniqueSlugify

# Settings for this script. Should be parametrized later.
# POSTSDIR = "blogs/cno/posts"
# OUTPUTDIR = "blogs/cno/out"
# TEMPLATEDIR = "blogs/cno/templates"
DEFAULT_LOCALE = "de_DE"


# TODO: Use config file in current directory instead
POSTSDIR = "posts"
OUTPUTDIR = "out"
TEMPLATEDIR = "templates"


# Output format
# the "-" in %-d will remove the leading 0 (if any)
FMT_DATE_OUTPUT = "%A, %-d. %B %Y"

IGNOREFILES = ["README", "TEMPLATE"]  # , "helloworld"]
EXTENSIONS = [".md"]
OUTPUT_EXTENSION = ".html"

# Set up logging
log_formatter = logging.Formatter('%(message)s')
# DEFAULT_LOGLEVEL = logging.WARNING
DEFAULT_LOGLEVEL = logging.DEBUG
log = logging.getLogger()
log.setLevel(DEFAULT_LOGLEVEL)

# Set locale to de_DE to get german output (day of week, ...)
locale.setlocale(locale.LC_ALL, "de_DE")

# Define slugify
# see: https://pypi.org/project/awesome-slugify/
slugify = UniqueSlugify()


class Post:
    """This object represents a post.

    A post object does not only contain the post's contents (text) but does
    also have some meta information such as the title, the post's publish date
    and the post's author (and maybe others).

    Each post is represented as a markdown file in the file system.
    """

    # Source file name (Markdown file of post)
    __filename: str = ""

    # Full path of the output filename
    __outfile: str = ""

    # Post neigbors
    __next: Post = None
    __prev: Post = None

    # Name of the (output) file
    # Will be derived from the input filename
    __slug: str = None

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
    __date: datetime = None

    # Human-readable string representing the date, i.e.
    # "Donnerstag, 3. August 2023"
    printable_date: str = ""

    # If post is a draft
    # This literally means that this script ignores this post
    __draft: bool = False

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

        # First read the contents of the file before
        # saving just the file's basename
        log.info("Read file contents")
        self.raw = self.__read_file(full_filename)

        # Store the basename
        self.__filename = os.path.basename(full_filename)

        # Get the meta information and the raw text
        self.meta, self.raw_text = self.__segment(self.raw)

        # Render the text to HTML
        self.rendered_text = self.__render(self.raw_text)

        # Set additional attributes
        self.__parse_attributes(self.meta)

    # Define properties ("getters") to get daata from the meta dictionary.
    # If a specified property does not exist in the dictionary the getter
    # functions must return a meaninungful value.

    @property
    def title(self) -> str:
        return self.meta.get("title", "Untitled")

    @property
    def date(self) -> datetime:
        return self.__date

    @property
    def isodate(self) -> str:
        return self.date.astimezone().isoformat()

    @property
    def basename(self) -> str:
        return os.path.basename(self.filename)

    @property
    def slug(self) -> str:
        if not self.__slug:
            self.__slug = slugify(
                    os.path.splitext(self.basename)[0],
                    to_lower=True,
                    )
        return self.__slug

    @property
    def filename(self) -> str:
        return self.__filename

    @property
    def outfile(self) -> str:
        return f"{self.slug}{OUTPUT_EXTENSION}"

    @property
    def html(self) -> str:
        return self.rendered_text

    @property
    def draft(self) -> bool:
        return "draft" in self.meta.keys()

    @property
    def next(self) -> Post:
        return self.__next

    @next.setter
    def next(self, post: Post):
        self.__next = post

    def has_next(self) -> bool:
        return self.__next is not None

    @property
    def prev(self) -> Post:
        return self.__prev

    @prev.setter
    def prev(self, post: Post):
        self.__prev = post

    def has_prev(self) -> bool:
        return self.__prev is not None

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
            self.__date = self.__parse_date(header["date"])
            if not self.__date:
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
        self.__date == self.__parse_date(meta["date"])
        if self.__date:
            self.printable_date = self.__create_printable_date(self.date,
                                                               self.lang)

        # draft
        self.__draft = ("draft" in meta.keys())
        if self.__draft:
            log.debug("Mark as draft")

    def __parse_date(self,
                     prefix_date: str) -> datetime:
        """
        """
        log.debug(f"Create printable date from {prefix_date}")

        # Supported input formats
        supported_formats: list[str] = [
                "%d.%m.%y",     # 01.01.23
                "%d.%m.%Y",     # 01.01.2023
                ]

        dt: datetime = None

        for fmt in supported_formats:
            try:
                dt = datetime.strptime(prefix_date, fmt)
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
                                date: datetime,
                                locale: str = None) -> str:
        """

        """
        result: str = None
        if locale:
            try:
                with (self.setlocale(locale)):
                    result = date.strftime(FMT_DATE_OUTPUT)
            except Exception as e:
                log.warning(f"Could not create printable date in {self.lang}: "
                            f"{e}")

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

    # Representation functions

    def __str__(self):
        if self.date:
            shortdate = datetime.strftime(self.date, "%d.%m.%Y")
        else:
            shortdate = "UNSET_DATE"
        #return f"{shortdate} {self.title} ({self.filename} -> {self.slug})"
        return f"{self.title}"

    def __repr__(self):
        return str(self)

    # Comparison functions
    def __eq__(self, other: Post) -> bool:
        return self.date == other.date

    def __lt__(self, other: Post) -> bool:
        return self.date < other.date

    def __gt__(self, other: Post) -> bool:
        return self.date > other.date

    def __ne__(self, other: Post) -> bool:
        return self.date != other.date

    # Comprehensive information
    def to_dict(self) -> dict[str, str]:
        result: dict[str, str] = {}
        result["title"] = self.title
        result["date"] = self.date
        result["printable_date"] = self.printable_date
        result["filename"] = self.filename
        result["outfile"] = self.outfile
        result["next"] = self.next
        result["prev"] = self.prev

        to_display: list[str] = [
                "author"
                ]
        for attribute in to_display:
            if attribute in self.meta:
                result[attribute] = self.meta.get(attribute)

        return result


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

    def create_blogchain(self,
                         path: str,
                         extensions: list[str],
                         ignore_files: list[str],
                         ) -> list[Post]:
        """Return list of post objects to be published sorted by the posts'
        publication date from newest to oldest (newest post is the first
        element in the list).
        Although this function returns a list you can iterate the chain of Post
        objects by the Post's member functions .next() and .previous().

        :param path:            File system path where the markdown files are
                                located
        :type path:             str
        :param extenstions:     List of extensions the markdown files can have
        :type extensions:       list[str]
        :param ignore_files:    List of files' (basenames) to ignore
        :type ignore_files:     list[str]
        :return:                List of Post Objects, the newest post first
        :rtype:                 list[Post]
        """
        # Will hold the post objects
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
        # Sorted list uses the Post's built-in comparison functions.
        # You could also achieve the same by using "key=lambda p: p.date"
        list_of_post_objects = sorted(list_of_post_objects,
                                      reverse=True)

        log.debug(f"Chain-link {len(list_of_post_objects)} objects")
        for i in range(0, len(list_of_post_objects)):
            post = list_of_post_objects[i]

            # Set previous post objectt
            if i == 0:
                post.prev = None
            else:
                post.prev = list_of_post_objects[i - 1]

            # Set next post object
            if i == len(list_of_post_objects) - 1:
                post.next = None
            else:
                post.next = list_of_post_objects[i + 1]

        return list_of_post_objects

    def create_html(self,
                    post: Post,
                    template_file: str,
                    ) -> str:
        """Create the contents of an HTML file for a particular post using a
        particular template.

        :param post:            Post to write
        :type post:             Post
        :param template_file:   Template file to use for creating HTML
        :type template_file:    str
        :return:                Content of HTML file based on template file
        :rtype:                 str
        """
        log.info(f"Create HTML for {post} from {template_file}")

        log.debug("Create data dictionary")
        data: dict[str, str] = {
                "title": post.title,
                "date": post.printable_date,
                "text": post.rendered_text,
                "outfile": post.outfile,
                "next": post.next,
                "prev": post.prev,
                }

        log.debug("Create Jinja2 environment and load template")
        environment = Environment(
                loader=FileSystemLoader(TEMPLATEDIR)
                )
        template = environment.get_template(template_file)

        log.debug("Render content")
        content = template.render(data)
        return content

    def create_atom_feed(self,
                         blogchain: list[Post],
                         ) -> str:
        """Create Atom Feed.
        """
        environment = Environment(
                loader=FileSystemLoader(TEMPLATEDIR)
                )
        template = environment.get_template("atom.xml")

        blog: dict[str, str] = {}
        blog["title"] = "On the Heights of Despair"
        blog["subtitle"] = "The very long journey of a man called me."
        blog["author"] = "Niels Fallenbeck"
        blog["id"] = "https://fallenbeck.com/"
        blog["url"] = "https://fallenbeck.com/"
        blog["feedurl"] = "https://fallenbeck.com/atom.xml"
        blog["icon"] = "https://fallenbeck.com/favicon.ico"
        blog["generator"] = "Blogchain"
        blog["generator_uri"] = "https://fallenbeck.com/"
        blog["date"] = blogchain[0].isodate

        content = template.render({
            "blog": blog,
            "posts": blogchain,
            })

        return content

    def main(self) -> None:
        """This is the main function that coordinates the run and writes the
        files to disk.
        """
        blogchain = self.create_blogchain(
                path=self.posts_directory,
                extensions=self.post_extensions,
                ignore_files=self.ignore_filenames,
                )

        log.warning(pprint.pformat(blogchain))

        log.info(f"Generated blogchain: {blogchain}")

        for post in blogchain:
            log.info(pprint.pformat(post.to_dict()))

            html_contents = self.create_html(
                    post=post,
                    template_file="index.html"
                    )

            with open(os.path.join(OUTPUTDIR, post.outfile), "w") as f:
                f.write(html_contents)

            if not post.prev:
                with open(os.path.join(OUTPUTDIR, "index.html"), "w") as f:
                    f.write(html_contents)

        with open(os.path.join(OUTPUTDIR, "atom.xml"), "w") as f:
            f.write(self.create_atom_feed(blogchain))


if __name__ == '__main__':
    pyl = PyLive()
