#!/bin/sh

usage ()
{
	cat <<EOF >&2
`basename $0` - madokami manga fetcher

usage: dl.sh [-dhv] <manga name> ...

options:
 -d  turn on debugging
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

match_vol ()
# $1 - list to grep
# $2 - vol # to match
{
	# first fmt chk: ^([]|<>|())tag -? name -? (())v
	# sec fmt chk: name -? v -? c -? ([]|<>|())tag (+ w/e).ext$
	echo "${1}" | grep -E                                 \
	"^((\[|<|\().+(\]|>|\)))?(\s*-?\s*)?\(?v0*\)?${2}" || \
	echo "${dls}" | grep -E                               \
	"\(?v0*${2}\)?(\s*-?ch?\s*[0-9,-]+)?(\s*-?(\[|<|\().+(\]|>|\))\s*)?(\s*+\s*.+)?\..+$"

	return $(($? ? 1 : 0))
}

filter_match ()
# $1 - file ls to filter
# $2 - vol/ch we are checking
{
	local pfx='filter_match():'
	[ -z "${1}" ] && return 1
	# for now we will always pick the first line
	local fls="${1}"
	echo "${PREF}" | while read prefln; do
	case "${prefln}" in
		tag*) # one of: () <> [] {}
			fls=`echo "${fls}" | grep -E "(\(|<|\[|\{)${prefln#* }(\)|>|\|\}])"` \
			|| { ver "${pfx} couldn't find tag: ${prefln#* } for $2" ; return 1 ;}
		;;
		type*) # one of: zip rar cbz cbr
			#ver "T!!!\n-----\n${fls}\n-----"
			fls=`echo "${fls}" | grep -Ei "\.${prefln#* }$"` \
			|| { ver "${pfx} couldn't find any ${prefln#* }'s for $2" ; return 1 ;}
			# TODO: ^^ specify for what vol/ch
		;;
		*) break #echo "${1}" | sed 1q || return 1
		;;
	esac
	done
	local caseret=$?
	echo "${fls}" | sed 1q

	return ${caseret} # XXX chk if OK
}

parse_req_files ()
{
	if [ "$1" = 'all' ]; then
		doall=1 ; export doall
		return 0
	fi
	echo "${1}" "${2}" | \
	awk -v d=${d} \
	'
		BEGIN { pfx="awk: parse_req_files():" }
		{
			if (NF > 2) {
				print pfx, "too many args" >"/dev/stderr"
				exit(1)
			}
			for (nftmp=1; nftmp <= NF; nftmp++) {
				# before doing anything, check for invalid
				# chars, then check for invalid use of valid chars
				if ($nftmp !~ /^[volch0-9,-]+$/) {
					print pfx, "bad field", "`"$nftmp"`" >"/dev/stderr"
					exit(1)
				} else if ($nftmp !~ /^(v(ol)?|ch?)[0-9-]/) {
					print pfx, "bad field", "`"$nftmp"`" >"/dev/stderr"
					exit(1)
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
				if (d) { print dpfx, delim[1], "sum -", sum >"/dev/stderr" }
				if (num[i] < sum) {
					print pfx, delim[1], "must be in ascending order" >"/dev/stderr"
					exit(1)
				} sum += (delim[i] == "-" ? num[i] : 1)
			}
			sum = numA[1]
			for (i = 2; i <= length(numA); i++) {
				if (d) { print dpfx, delimA[1], "sum -", sum >"/dev/stderr" }
				if (numA[i] < sum) {
					print pfx, delimA[1], "must be in ascending order" >"/dev/stderr"
					exit(1)
				} sum += (delimA[i] == "-" ? numA[i] : 1)
			}
			for (i = 1; i <= length(delim); i++) {
				if (i == 1) {
					delim[1] == "v" ? v=1 : c=1
				} else if (delim[i] == "," && num[i] !~ /[0-9]+/) {
					print pfx, "extraneous comma in", delim[1] >"/dev/stderr"
					exit(1)
				}
			}
			for (i = 1; i <= length(delimA); i++) {
				if (i == 1) {
					if (v) { c=1 } else v=1
				} else if (delimA[i] == "," && numA[i] !~ /[0-9]+/) {
					print pfx, "extraneous comma in", delimA[1] >"/dev/stderr"
					exit(1)
				}
			}
			for (i = 1; i <= length(delim); i++)
				printf "%s %s ", delim[i], num[i]
			printf "\n"
			if (v && c) {
				for (i = 1; i <= length(delimA); i++)
					printf "%s %s ", delimA[i], numA[i]
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
		case `echo "${1}" | wc -l | tr -d '[:space:]'` \
		in
		1) ver "attempting download of ${1} ..."         ;;
		*) ver "attempting dl list:\n-----\n${1}\n-----" ;;
		esac
		ver "would curl https://manga.madokami.com/${dir}/${1}" # -o ${PREFIX}/${1}"
		#echo "${1}" | while read f; do
		#	curl -sL                                 \
		#	-u "${user}:${pass}"                     \
		#	"https://manga.madokami.com/${dir}/${f}" \
		#	-o "${PREFIX}/${f}" && \
		#	cdl="$(printf "%s\n%s" "${cdl}" "${f}")"
		#done

		return $?
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
	parse_req_files "$2" "$3" | \
	while read req; do
		dbg "\$req - ${req}"
		if [ "${req%% *}" = 'v' ]; then
			dbg 'v match'
			local curnum=`echo ${req} | cut -f2 -d' '`
			dbg "\$curnum - ${curnum}"
			match=`match_vol "${dls}" ${curnum}`         && \
			filtm=`filter_match "${match}" vol${curnum}` && \
			dbg "match:\n-----\n${match}\n-----"         && \
			dbg "filtm:\n-----\n${filtm}\n-----"         && \
			{ curl_http "${filtm}" \
			  || die "failed to download ${filtm}" ;} || \
			ver "no match for vol${curnum}, continuing check on later vols..."
			local curf=2 lastn nxm
			while :; do
				: $((curf += 1))
				lastn=${curnum}
				curnum=`echo ${req} | cut -f${curf} -d' '`
				dbg "curf - ${curf} curnum - ${curnum} lastn - ${lastn}"
				[ -z "${curnum}" ] && break
				case ${curnum} in
				-)
					: $((curf += 1))
					curnum=`echo ${req} | cut -f${curf} -d' '`
					if [ -z "${curnum}" ]; then # open-end range
						local curl_oe_ls=""
						while :; do
							: $((lastn += 1))
							nxm=`match_vol "${dls}" ${lastn}`       && \
							fil=`filter_match "${nxm}" vol${lastn}` && \
							{ [ -z "${curl_oe_ls}" ] &&     \
							  curl_oe_ls="${fil}"    ||     \
							  curl_oe_ls="$(printf "%s\n%s" \
							  "${curl_oe_ls}" "${fil}")" ;}
							case $? in
							1) ver
							  "no filtered match for vol${lastn}, cont. check for"
							  "later vols..." ; continue
							;;
							2)
							esac
						done
						dbg "curling oe-range, v${lastn}-"
						curl_http "${curl_oe_ls}"
					else
						dbg 'in closed range'
						while [ ${lastn} -lt ${curnum} ]; do
							: $((lastn += 1))
							nxm=`match_vol "${dls}" "${lastn}"`     &&        \
							fil=`filter_match "${nxm}" vol${lastn}` ||        \
							{ ver                                             \
							  "no match for vol${lastn}, continuing check on" \
							  "later vols..." ; continue ;}
							dbg "fil - ${fil}"
							curl_http "${nxm}"
						done
					fi
					;;
				*) die 'curnum is:' "v ${curnum}"
				   ;;
				esac
			done
		elif [ "${req%% *}" = 'c' ]; then
			dbg 'c match'
		else # fallthru
			die 'use_curl(): while read req fallthru'
		fi
	done
}

# TODO:
# - better handling for multiple search matches
# - add checks for multi-part vols e.g. vol1 (1 of 3)
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
PREF='type zip' # FIXME: tag not working
: ${PREFIX:=/tmp}

trap 'echo;die "caught signal"' SIGINT SIGKILL SIGABRT

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
	*) use_curl "$1" "$2" "$3"
	   test -n "$3" ; shift $(($? ? 2 : 3))
	;;
	esac
done

exit 0
