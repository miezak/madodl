## [v0.2.3] - 2016-11-13
### Fixed
* Bug in `parsers.py` that caused a regex-mismatch error in wild number handling logic.

## [v0.2.2] - 2016-11-10
### Fixed
* Updated domain to `.al`
* `parsers.py`: Fixed a bug in the `RNG` regex that caused a `.` character placed directly in-front of the extension to be incorrectly interpreted as a `RNG` token.
* All download requests are now (hopefully) properly percent-encoded.
* Don't display sub-directories in query output.

### Changed
* FTP LISTings are now fetched with the `nocwd` cURL option. This adds a noticable speed increase when looking up the directory listing remotely.
* Lots of style changes.
* Various non-functional code changes.
* Small message output changes for clarity.

## [v0.2.1] - 2016-04-27
### Fixed
* `apply_tag_filters()` regression.
* Bug that caused individual chapter requests to fail.

## [v0.2.0] - 2016-04-24
### Added
* Prefix program name to all message output.
* Implement the `for` sub-option from the config file.

### Changed
* Separate `madodl.py` into logically divided modules (files).
* Lots of style changes, including an attempt to conform to PEP recommendations.
* `util.py`: split `common_elem()` into two functions.
* Explicitly import madodl modules. With this change `madodl` _must_ be re-installed after every update.

### Fixed
* Various typos.
* Handle complete archive files with no prefix that are the only file.
* `ParseFile`: Don't leave `NUM` tokens that aren't volume/chapter numbers in `float()` format.
* Various bug fixes in `apply_tag_filters()`.

## [v0.1.1] - 2016-03-15
### Fixed
* ParseFile() chapter range (with no prefix) bug fix.
* Fix volume overmatch checking regression from v0.1.0

## [v0.1.0] - 2016-03-15
### Added
* Add a note in `config.yml` about the `for` suboption.

### Changed
* Change how non-increasing ranges are handled.
* Allow for a fractional in the range opening for requests.
* Always use template strings over the old-style \`%\` operator for string formatting.
* Several optimizations.
* Removed a verbose message leftover from testing.

### Fixed
* Fix a bug in ParseRequest() where chapters were being incorrectly converted to numbers.

## [v0.1.0a5] - 2016-03-07
### Added
* `prefer` and `not prefer` tag filter logic.

### Changed
* Rewrite match\_dir() recursively.
* Remove extraneous backslashes from code.

### Fixed
* Various volume and chapter selection fixes.

## [v0.1.0a4] - 2016-02-26
### Added
* Output the title of the series currently being downloaded in the curses output

### Fixed
* Handle chapters without a prefix
* Fix the {filter: out} config option.
* Remove the req.ALL number from the volume/chapter requests. This is used
to identify an open-ended range in the request. This fixes the erroneous
message \`can't find (vol/chp) 4294967296.0\`.

## [v0.1.0a3] - 2016-02-25
### Added
* Support for complete archive downloads.
* Support for a logfile.
* No\_output config option now works.
* -s switch now works.
* Checks for Python version.

### Changed
* Better output\_file checks
* Small console output touchups
* Online query fallback when JSON search fails

### Fixed
* Catch user signals properly.

## [v0.1.0a2] - 2016-02-22
### Added
* Support JSON directory listing file searching.

### Changed
* Refactor main\_loop(). The directory listing logic was moved to a separate
function.

### Fixed
* Check for Windows config file properly.

## [v0.1.0a1] - 2016-02-20
### Fixed
* Various ParseRequest() problems.

## v0.1.0a0 - 2016-02-20
Initial alpha release.

[v0.2.3]: https://github.com/miezak/madodl/compare/v0.2.2...v0.2.3
[v0.2.2]: https://github.com/miezak/madodl/compare/v0.2.1...v0.2.2
[v0.2.1]: https://github.com/miezak/madodl/compare/v0.2.0...v0.2.1
[v0.2.0]: https://github.com/miezak/madodl/compare/v0.1.1...v0.2.0
[v0.1.1]: https://github.com/miezak/madodl/compare/v0.1.0...v0.1.1
[v0.1.0]: https://github.com/miezak/madodl/compare/v0.1.0a5...v0.1.0
[v0.1.0a5]: https://github.com/miezak/madodl/compare/v0.1.0a4...v0.1.0a5
[v0.1.0a4]: https://github.com/miezak/madodl/compare/v0.1.0a3...v0.1.0a4
[v0.1.0a3]: https://github.com/miezak/madodl/compare/v0.1.0a2...v0.1.0a3
[v0.1.0a2]: https://github.com/miezak/madodl/compare/v0.1.0a1...v0.1.0a2
[v0.1.0a1]: https://github.com/miezak/madodl/compare/v0.1.0a0...v0.1.0a1
