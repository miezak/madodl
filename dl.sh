#!/bin/sh

usage ()
{
	cat <<EOF >&2
`basename $0` - madokami manga fetcher

usage: dl.sh [-dhv] [-p pref val] <manga name> ...

options:
 -d  turn on debugging
 -p  add a preference filter
 -v  verbose output
 -h  this output
EOF

	exit 0
}

dbg ()
# $@ - debug msg(s)
{
	if [ $d -eq 1 ]; then
		echo -e "dbg: $@" >&2
	fi

	return 0
}

ver ()
# $@ - verbose msg(s)
{
	if [ $v -eq 1 ]; then
		echo -e "verbose: $@" >&2
	fi

	return 0
}

die ()
# [$@] - error msg(s)
{
	[ -n "$1" ] && echo -e "die(): ERROR: $@" >&2

	exit 1
}

match_all ()
# $1 - list to grep
{
	echo "${1}" | grep -Ei '(\(|<|\[|\{)complete(\)|>|\]|\})'

	return $?
}

match_vol ()
# $1 - list to grep
# $2 - vol # to match
# ret - 0 on match, 1 on no match
{
	# first fmt chk: ^([]|<>|())tag -? name -? (())v$2
	# sec fmt chk: name -? v$2 -? c -? ([]|<>|())tag (+ w/e).ext$
	echo "${1}" | grep -Ei                                \
	"^((\[|<|\().+(\]|>|\)))?(\s*-?\s*)?.+\s+\(?v(ol(ume)?)?0*${2}[^0-9-]\)?" || \
	echo "${1}" | grep -Ei                                \
	".+\s+\(?v(ol(ume)?)?0*${2}[^0-9-]\)?(\s*-?c(h(apter)?)?\s*[0-9,-]+)?(\s*-?(\[|<|\().+(\]|>|\))\s*)?(\s*+\s*.+)?\..+$"

	return $?
}

match_vol_range ()
# $1 - list to grep
# $2 - first vol in range
# $3 - last vol in range
# ret - 0 on match, 1 on no match
{
	[ -z "${3}" ] && set "${1}" "${2}" '[0-9]+'
	# first fmt chk: ^([]|<>|())tag -? name -? (())v$2-$3
	# sec fmt chk: name -? v$2-$3 -? c -? ([]|<>|())tag (+ w/e).ext$
	echo "${1}" | grep -Ei                                \
	"^((\[|<|\().+(\]|>|\)))?(\s*-?\s*)?.+\s+\(?v(ol(ume)?)?0*${2}-0*${3}\)?" || \
	echo "${1}" | grep -Ei                                \
	".+\s+\(?v(ol(ume)?)?0*${2}-0*${3}\)?(\s*-?c(h(apter)?)?\s*[0-9,-]+)?(\s*-?(\[|<|\().+(\]|>|\))\s*)?(\s*+\s*.+)?\..+$"

	return $?
}

match_chap ()
# $1 - list to grep
# $2 - vol # to match
# ret - 0 on match, 1 on no match
{
	# first fmt chk: ^([]|<>|())tag -? name -? ((v)) c$2
	# sec fmt chk: name -? v -? c$2 -? ([]|<>|())tag (+ w/e).ext$
	echo "${1}" | grep -Ei                                \
	"^((\[|<|\().+(\]|>|\)))?(\s*-?\s*)?.+\s+\(?(v(ol(ume)?)?\d+)?c(h(apter)?)?${2}\)?" || \
	echo "${1}" | grep -Ei                                \
	".+\s+\(?v(ol(ume)?)?c(h(apter)?)?0*${2}\)?(\s*-?(\[|<|\().+(\]|>|\))\s*)?(\s*+\s*.+)?\..+$"

	return $?
}

filter_match ()
# $1 - file ls to filter
# $2 - vol/ch we are checking
# return 0 on match, 1 on no match, and 2 on initial empty list
{
	local pfx='filter_match():'
	[ -z "${1}" ] && return 2

	# for now we will always pick the first line

	local fls="${1}"
	export fls

	echo "${PREF}" |   \
	awk -v d="${d}"    \
		-v what="${2}" \
	'
		BEGIN {
			ret = fltidx = 0 ; fls = ENVIRON["fls"]
			split(fls, flsarr, /\n/)
			if (d) pfx = "dbg: filter_match():"
		}
		function dbg(msg) { if (d) print "dbg: filter_match(): "msg >"/dev/stderr" }
		function filter() {
			if ($1 == "tag") {
				IGNORECASE = 1 # XXX may not work with older awks
				ret = fls ~ "(\\(|<|\\[|\\{)"$2"(\\)|>|\\]|\\})"
			} else if ($1 == "type") {
				IGNORECASE = 1
				ret = fls ~ "\\."$2"$"
			} else return 1

			return ret
		}
		{
			idx = 1
			while ((fls = flsarr[idx++]))
				if (filter())
					fltarr[fltidx++] = fls
			if (!length(fltarr)) {
				if ($1 == "tag") {
					dbg("couldn`t find tag: "$2" for "what)
				} else if ($1 == "type") {
					dbg("couldn`t find any "$2"`s for "what)
				}
				exit(1)
			}
		}
		END {
			if (what == "all archives")
				for (i=0;i<length(fltarr);i++)
					print fltarr[i]
			else
				print fltarr[0]
		}
	'

	return $?
}

get_largest_range ()
# $1 - list of ranges
{
	echo "${1}" | \
	awk           \
	'
	BEGIN {
		if (NR == 1) {
			line = $0
			exit(0)
		}
		biggest = -1
	}
	{
		match($0, /v(ol(ume)?)?[0-9]+-[0-9]+/)
		range=substr($0, RSTART, RLENGTH)
		if ((n=substr(range, index(range, "-")+1)) > biggest) {
			biggest = n
			line = $0
		}
	}
	END { print line, biggest }
	'

	return 0
}

parse_req_files ()
{
	if [ "$1" = 'all' ]; then
		echo 'all'
		return 0
	fi
	echo "${1}" "${2}" | \
	awk -v d=${d} \
	'
		function dbg(msg) { if (d) print "dbg: "pfx" "msg >"/dev/stderr" }
		function die(msg) { print pfx" die(): "msg ; exit(1) }
		BEGIN { pfx="parse_req_files():" }
		{
			if (NF > 2)
				die("too many args")
			for (nftmp=1; nftmp <= NF; nftmp++) {
				# before doing anything, check for invalid
				# chars, then check for invalid use of valid chars
				if ($nftmp !~ /^[volch0-9,-]+$/) {
					die("bad field `"$nftmp"`")
				} else if ($nftmp !~ /^(v(ol)?|ch?)[0-9-]/) {
					die("bad field `"$nftmp"`")
				}
				if (length(num)) {
					for (i in num)
						numA[i] = num[i]
					for (i in delim)
						delimA[i] = delim[i]
					delete numtmp ; delete delimtmp
					delete num ; delete delim
				}
				gsub(/[olh]/, "", $nftmp)
				split($nftmp, numtmp, /[^0-9]/)
				split($nftmp, delimtmp, /[0-9]+/)
				# because split() leaves the delim chars
				# in the created numay as empty strings
				# they need to be removed
				j=1
				for (i = 1; i <= length(numtmp); i++)
					if (numtmp[i] != "")
						num[j++] = numtmp[i]
				j=1
				for (i = 1; i <= length(delimtmp); i++)
					if (delimtmp[i] != "")
						delim[j++] = delimtmp[i]
				for (i in delim)
					if (length(delim[i]) != 1) {
						print pfx, "too many separators" >"/dev/stderr"
						exit(1)
					}
			}
			if (d) {
				dpfx = "dbg: "pfx
				dsp = "                            "
				print dpfx, "num" >"/dev/stderr"
				for (i=1;i<=length(num);i++)
					print dsp, "idx"i" -", num[i] >"/dev/stderr"
				print dpfx, "delim" >"/dev/stderr"
				for (i=1;i<=length(delim);i++)
					print dsp, "idx"i" -", delim[i] >"/dev/stderr"
				print dpfx, "numA" >"/dev/stderr"
				for (i=1;i<=length(numA);i++)
					print dsp, "idx"i" -", numA[i] >"/dev/stderr"
				print dpfx, "delimA" >"/dev/stderr"
				for (i=1;i<=length(delimA);i++)
					print dsp, "idx"i" -", delimA[i] >"/dev/stderr"
			}
			sum = num[1]
			for (i = 2; i <= length(num); i++) {
				dbg(delim[1]" sum - "sum)
				if (num[i] < sum)
					die(delim[1]" must be in ascending order")
				sum += (delim[i] == "-" ? num[i] : 1)
			}
			sum = numA[1]
			for (i = 2; i <= length(numA); i++) {
				dbg(delimA[1]" sum - "sum)
				if (numA[i] < sum)
					die(delimA[1]" must be in ascending order")
				sum += (delimA[i] == "-" ? numA[i] : 1)
			}
			for (i = 1; i <= length(delim); i++) {
				if (i == 1) {
					delim[1] == "v" ? v=1 : c=1
				} else if (delim[i] == "," && num[i] !~ /[0-9]+/) {
					die("extraneous comma in "delim[1])
				}
			}
			for (i = 1; i <= length(delimA); i++) {
				if (i == 1) {
					if (v) { c=1 } else v=1
				} else if (delimA[i] == "," && numA[i] !~ /[0-9]+/) {
					die("extraneous comma in "delimA[1])
				}
			}
			if (v && c) {
				# always print vol first
				if (delim[1] == "v") {
					for (i = 1; i <= length(delim); i++)
						printf "%s %s ", delim[i], num[i]
					printf "\n"
					for (i = 1; i <= length(delimA); i++)
						printf "%s %s ", delimA[i], numA[i]
					printf "\n"
				} else {
					for (i = 1; i <= length(delimA); i++)
						printf "%s %s ", delimA[i], numA[i]
					printf "\n"
					for (i = 1; i <= length(delim); i++)
						printf "%s %s ", delim[i], num[i]
					printf "\n"
				}
			} else {
				for (i = 1; i <= length(delim); i++)
					printf "%s %s ", delim[i], num[i]
				printf "\n"
			}
		}
	'
}

use_curl ()
{
	curl_http ()
	# $1 - file(s) to dl
	{
		ver "attempting download of:\n-----\n${1}\n-----"
		# we need a named pipe here to preserve the modified $cdl
		# outside of the pipeline
		[ -z "${np}"   ] && die 'BUG: use_curl(): curl_http(): no fifo'
		[ -z "${PATH}" ] && die 'BUG: use_curl(): curl_http(): no PATH'
		echo "${PATH}" > "${np}" &
		echo "${1}"    > "${np}" &
		while read -r f; do
			if [ "${f}" = "${PATH}" ]; then
				PATH="${f}" ; export PATH
				continue
			fi
		ver "would curl https://manga.madokami.com/${dir}/${f}" # -o ${PREFIX}/${1}"
			if [ -z "${cdl}" ]; then
				cdl="${f}"
			else
				cdl="$(printf "%s\n%s" "${cdl}" "${f}")"
			fi
		#	curl -sL                                 \
		#	-u "${user}:${pass}"                     \
		#	"https://manga.madokami.com/${dir}/${f}" \
		#	-o "${PREFIX}/${f}" && \
		#	cdl="$(printf "%s\n%s" "${cdl}" "${f}")"
		done < "${np}"

		if [ $? -ne 0 ]; then
			die "curl_http(): curl failed"
		fi

		return 0
	}
	local dir=$(                                          \
	curl -sL "https://manga.madokami.com/search?q=${1}" | \
	awk -v v=${v}                                         \
	'
		BEGIN { vp = "verbose:" }
		/href="\/"/ {
			if ((n=substr($0, length($0)-2)) == "(0)") {
				print "no matches found" >"/dev/stderr"
				exit(1)
			} else if (n != "(1)") {
				if (v)
					print vp, "multiple matches found, using first" >"/dev/stderr"
			}
			while (getline) {
				if ($0 ~ /<td>/) {
					match($0, /href=".+"/)
					print substr($0, RSTART+6, RLENGTH-7)
					exit(0)
				}
			}
		}
	')
	[ -z "${dir}" ] && die '$dir empty'
	dbg "dir - ${dir}"
	ver "curling dir listing..."
	dls="$(curl -sk --ftp-ssl --list-only \
	"ftp://${FTPS_USER}:${FTPS_PASS}@manga.madokami.com:${FTPS_PORT}${dir}/" \
	| sort -n)" # keep it num sorted
	[ -z "${dls}" ] && die 'no files found!'
	dbg "files:\n-----\n${dls}\n-----"
	local cdl=""
	rnd=`awk -v min=5 -v max=9999 \
	    'BEGIN {srand() ; print int(min+rand()*(max-min+1))}'`
	np=`printf "%s/madodl.%s" "${TMPDIR:-/tmp}" "${rnd}"`
	mkfifo "${np}"
	[ $? -ne 0 ] && die 'use_curl(): failed to create fifo'
	parse_req_files "$2" "$3" | \
	while read req; do
		dbg "\$req - ${req}"
		if [ "${req}" = 'all' ]; then
			dbg 'all match'
			# first look for complete collection
			compar=`match_all "${dls}"`
			case $? in
			0)
				ver 'found a complete collection'
				filtm=`filter_match "${compar}" 'complete archives'` || \
				die 'BUG: filter_match() returned' "${?}"
			;;
			1)
				ver 'No complete archive found. Filtering whole listing...'
				filtm=`filter_match "${dls}" 'all archives'` || \
				die 'BUG: filter_match() returned' "${?}"
			;;
			2) break ;;
			esac
			curl_http "${filtm}"
			break
		elif [ "${req%% *}" = 'v' ]; then
			dbg 'v match'
			match="" filtm="" # ensure these are always cleared
			local curnum=`echo ${req} | cut -f2 -d' '`
			local firstnum=${curnum}
			dbg "\$curnum - ${curnum}"
			match=`match_vol "${dls}" ${curnum}`         && \
			filtm=`filter_match "${match}" vol${curnum}` && \
			dbg "match:\n-----\n${match}\n-----"         && \
			dbg "filtm:\n-----\n${filtm}\n-----"         || \
			ver "no filtered match for vol${curnum}," \
			    "cont. check on later vols..."
			local curf=2 lastn nxm="" fil=""
			while :; do
				: $((curf += 1))
				lastn=${curnum}
				curnum=`echo ${req} | cut -f${curf} -d' '`
				dbg "curf - ${curf} curnum - ${curnum} lastn - ${lastn}"
				if [ -z "${curnum}" ]; then # no range
					[ -n "${filtm}" ] && curl_http "${filtm}"
					break
				fi
				case ${curnum} in
				-)
					: $((curf += 1))
					curnum=`echo ${req} | cut -f${curf} -d' '`
					if [ -z "${curnum}" ]; then # open-end range
						local curl_oe_ls="" ret
						nxm=`match_vol_range "${dls}" "${firstnum}"`
						if [ $? -eq 0 ]; then
							lr=`get_largest_range "${nxm}"`
							fil=`filter_match "${lr%% *}" vol1-${lr##* }`
							lastn=`expr ${lr##* } + 1`
							curl_oe_ls="${fil}"
						else
							[ -n "${filtm}" ] && curl_oe_ls="${filtm}"
						fi
						while :; do
							: $((lastn += 1))
							nxm=`match_vol_range "${dls}" "${lastn}"`
							if [ $? -eq 0 ]; then
								lr=`get_largest_range "${nxm}"`
								fil=`filter_match "${lr%% *}" vol1-${lr##* }`
								lastn=`expr ${lr##* } + 1`
								dbg 'LRLASTNINF' "${lastn}"
							else
								nxm=`match_vol "${dls}" ${lastn}`
								fil=`filter_match "${nxm}" vol${lastn}`
							fi
							case "$?" in
							0)
								[ -z "${curl_oe_ls}" ] &&     \
								curl_oe_ls="${fil}"    ||     \
								curl_oe_ls="$(printf "%s\n%s" \
								                     "${curl_oe_ls}" "${fil}")"
							;;
							1) ver                                             \
							  "no filtered match for vol${lastn}, cont. check" \
							  "for later vols..." ; continue
							;;
							2) : $((lastn -= 1))
							   ver "last match - vol${lastn}"
							   break
							;;
							*) die 'unexpected return value' "${ret}"
							esac
						done
						[ -z "${curl_oe_ls}" ] && break
						dbg "curling oe-range"
						curl_http "${curl_oe_ls}"
					else
						dbg 'in closed range'
						# first check for a multi-vol archive
						nxm=`match_vol_range "${dls}" "${firstnum}" \
						                     "${curnum}"`             && \
						fil=`filter_match "${nxm}" \
						                  "vol${firstnum}-${curnum}"` && \
						dbg 'cr multi-vol match' && \
						curl_http "${fil}"       || \
						while [ ${lastn} -lt ${curnum} ]; do
							: $((lastn += 1))
							# first check for a multi-vol archive
							nxm=`match_vol_range "${dls}" "${lastn}" \
							                     "${curnum}"` && \
							fil=`filter_match "${nxm}" \
							                  "vol${lastn}-${curnum}"`   &&   \
							dbg 'matched a multi-vol archive'            &&   \
							curl_http "${fil}" && break                  ||   \
							{ nxm=`match_vol "${dls}" "${lastn}"` && \
							  fil=`filter_match "${nxm}" vol${lastn}` ;} ||   \
							{ ver                                             \
							  "no match for vol${lastn}, continuing check on" \
							  "later vols..." ; continue ;}
							curl_http "${fil}"
						done
					fi
					;;
				*) die 'use_curl(): BUG: bad vol range'
				   ;;
				esac
			done
		elif [ "${req%% *}" = 'c' ]; then
			dbg 'c match'
			local curnum=`echo ${req} | cut -f2 -d' '`
			dbg 'curnum' "${curnum}"
			dbg "CDL" "${cdl}"
			if ! match_chap "${cdl}" "${curnum}"; then
				ver "ch${curnum} was already downloaded, skipping..."
				continue
			fi
		else # fallthru
			die 'use_curl(): BUG: while read req fallthru'
		fi
	done
}

chk_pref ()
# [$1] - preference to check against
# [$2] - value of $1 preference
{
	local pfx='chk_pref():'
	echo "${PREF}" |                                   \
	awk -v pfx="${pfx}" -v add="${1}" -v addval="${2}" \
	'
		BEGIN {
			t_seen = ret = bpi = btv = 0
			valid_pref  = "^(t(ype|ag))$"
			valid_t_val = "^(zip|rar|cb(z|r))$"
			if (add) {
				if (add !~ valid_pref)
					badp[bpi++] = add
				if (add == "type" && addval !~ valid_t_val)
					badtval[btv++] = addval
			}
		}
		$1 ~ /^[[:space:]]*$/ { next }
		$1 == "type" {
			t_seen++
			if ($2 !~ valid_t_val) badtval[btv++] = $0
		}
		$1 !~ valid_pref { badp[bpi++] = $1 }
		END {
			if (t_seen && add == "type") {
				print pfx, "ERROR: type already defined"
				exit(1)
			} else if (t_seen > 1) {
				print pfx, "ERROR: type defined multiple times"
				exit(1)
			} else if (length(badp)) {
				print pfx, "ERROR: detected bad pref identifier(s):"
				for (p in badp)
					print "                   -", badp[p]
				exit(1)
			} else if (length(badtval)) {
				print pfx, "ERROR: detected bad type value:"
				for (pv in badtval)
					print "                                     -", badtval[pv]
				exit(1)
			}
			exit(0)
		}
	' || die

	return 0
}

add_pref ()
# $1, $2 - preference to add
{
	chk_pref "${1}" "${2}"
	[ -z "${PREF}" ] && PREF="${1} ${2}" \
	|| PREF=`printf "%s\n%s\n" "${PREF}" "${1} ${2}"`

	return 0
}


# TODO:
# - better handling for multiple search matches
# - add checks for multi-part vols e.g. vol1 (1 of 3)
# - add caching
# - _way_ too much code duplication
# - right now close ended range checks only look for $lastn .. $curnum
#                                                    (vol - lastvol)
# - better option handling
# - make the code less shitty

[ $# -eq 0 ] && usage
d=0 v=1
. dlp.sh # $user + $pass
FTPS_USER='homura'
FTPS_PASS='megane'
FTPS_PORT='24430'
#
# $PREF usage:
# <identifier> <value>[\n next pair ...]
#
# current identifiers:
# tag ...
# type <zip|rar|cbz|cbr>
# _must_ be space between ident and val
#
PREF=\
'
'
export PREF
: ${PREFIX:=/tmp}

trap 'echo;die "caught signal"' SIGINT SIGKILL SIGABRT

chk_pref

while [ -n "$1" ]
do
	dbg "in main while loop"
	case "$1" in
	-[dhv]|-d[hv]|-h[dv]|-v[dh]|-dhv|-dvh|-hdv|-hvd|-vdh|-vhd)
		[ -z "${1##*[d]*}" ] && d=1
		[ -z "${1##*[h]*}" ] && usage
		[ -z "${1##*[v]*}" ] && v=1
		shift
	;;
	-p)
		test -z "${2}" || test -z "${3}" && \
		die '-p needs 2 arguments'
		add_pref "${2}" "${3}"
		shift 3
	;;
	*)
		# always cut out empty lines
		PREF=`echo "${PREF}" | grep -v '^[[:space:]]*$'`
		use_curl "$1" "$2" "$3"
		test -n "$3" ; shift $(($? ? 2 : 3))
	;;
	esac
done

exit 0
