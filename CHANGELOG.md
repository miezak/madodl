## [v0.1.0] - 2015-03-15
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

[v0.1.0]: https://github.com/miezak/madodl/compare/v0.1.0a5...v0.1.0
[v0.1.0a5]: https://github.com/miezak/madodl/compare/v0.1.0a4...v0.1.0a5
[v0.1.0a4]: https://github.com/miezak/madodl/compare/v0.1.0a3...v0.1.0a4
[v0.1.0a3]: https://github.com/miezak/madodl/compare/v0.1.0a2...v0.1.0a3
[v0.1.0a2]: https://github.com/miezak/madodl/compare/v0.1.0a1...v0.1.0a2
[v0.1.0a1]: https://github.com/miezak/madodl/compare/v0.1.0a0...v0.1.0a1
