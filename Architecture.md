# Architecture

The basic idea is to have 

## Components

  * `pylive` as the management component to render and publish new posts
  * A _blog_ representing an an arbitrary amount of _post_ to be rendered
    and published
  * A _post_ can be written in Markdown format and needs to be rendered
    to static HTML output based on
  * a _template_ that defines the look and other data of the rendered post
    that will be published to
  * a _remote_ location either via scp or ftp.

### pylive

The software will work on _blog_-directories that represent a blog.
Every information needed to work with this blog needs to be within this
directory.

### Blog

A _blog_ is a set of files that specifies a single blog (duh!).
Blogs can be considered as objects _pylive_ needs to work with and will contain
all data and files needed to to so, in particular:

| **File or Directory** | **Contents** |
| --- | --- |
| `blog/` | main directory for the blog `blog` |
| `blog/config` | Configuration file for this particular blog |
| `blog/posts/` | Posts in Markdown format to be rendered |
| `blog/site/` | Static HTML files containing the rendered posts |
| `blog/template/` | Templates used to render the posts |



