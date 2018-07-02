#!/usr/bin/env python
# Python 2.7.x - 3.6.x
# LinkFinder
# By Gerben_Javado

# Fix webbrowser bug for MacOS
import os
os.environ["BROWSER"] = "open"

# Import libraries
import re, sys, glob, cgi, argparse, requests, urllib, jsbeautifier, webbrowser, subprocess, base64, xml.etree.ElementTree

from requests_file import FileAdapter
from string import Template
from requests.packages.urllib3.exceptions import InsecureRequestWarning 
from bs4 import BeautifulSoup 

base=None
# Parse command line
parser = argparse.ArgumentParser()
parser.add_argument("-i", "--input",
                    help="Input a: URL, file or folder. \
                    For folders a wildcard can be used (e.g. '/*.js').",
                    required="True", action="store")
parser.add_argument("-o", "--output",
                    help="Where to save the file, \
                    including file name. Default: output.html",
                    action="store", default="output.html")
parser.add_argument("-r", "--regex",
                    help="RegEx for filtering purposes \
                    against found endpoint (e.g. ^/api/)",
                    action="store")
parser.add_argument("-b", "--burp",
                    help="",
                    action="store_true")
parser.add_argument("-S", "--site",
                    help="Look for js file from url",
                    action="store_true")
parser.add_argument("-c", "--cookies",
                    help="Add cookies for authenticated JS files",
                    action="store", default="")
args = parser.parse_args()

# Newlines in regex? Important for CLI output without jsbeautifier
if args.output != 'cli':
    addition = ("[^\n]*","[^\n]*")
else:
    addition = ("","")

# Regex used
regex = re.compile(r"""

  (%s(?:"|')                    # Start newline delimiter

  (?:
    ((?:[a-zA-Z]{1,10}://|//)       # Match a scheme [a-Z]*1-10 or //
    [^"'/]{1,}\.                    # Match a domainname (any character + dot)
    [a-zA-Z]{2,}[^"']{0,})          # The domainextension and/or path

    |

    ((?:/|\.\./|\./)                # Start with /,../,./
    [^"'><,;| *()(%%$^/\\\[\]]       # Next character can't be... 
    [^"'><,;|()]{1,})               # Rest of the characters can't be

    |

    ([a-zA-Z0-9_\-/]{1,}/           # Relative endpoint with /
    [a-zA-Z0-9_\-/]{1,}\.[a-z]{1,4} # Rest + extension
    (?:[\?|/][^"|']{0,}|))          # ? mark with parameters

    |

    ([a-zA-Z0-9_\-]{1,}             # filename
    \.(?:php|asp|aspx|jsp)          # . + extension
    (?:\?[^"|']{0,}|))              # ? mark with parameters
 
  )             
  
  (?:"|')%s)                    # End newline delimiter

""" % addition, re.VERBOSE)

def parser_error(errmsg):
    '''
    Error Messages
    '''
    print("Usage: python %s [Options] use -h for help" % sys.argv[0])
    print("Error: %s" % errmsg)
    sys.exit()


def parser_input(input):
    '''
    Parse Input
    '''

    # Method 1 - URL
    if input.startswith(('http://', 'https://',
                         'file://', 'ftp://', 'ftps://')):
        base = input
        return [[input],base]

    # Method 2 - URL Inspector Firefox
    if input.startswith('view-source:'):
        return [input[12:]]

    # Method 3 - Burp file
    if args.burp:
        jsfiles = []
        items = xml.etree.ElementTree.fromstring(open(args.input, "r").read())
        
        for item in items:
            jsfiles.append({"js":base64.b64decode(item.find('response').text).decode('utf-8'), "url":item.find('url').text})
        return jsfiles

    # Method 4 - Folder with a wildcard
    if "*" in input:
        paths = glob.glob(os.path.abspath(input))
        for index, path in enumerate(paths):
            paths[index] = "file://%s" % path
        return (paths if len(paths) > 0 else parser_error('Input with wildcard does \
        not match any files.'))

    # Method 5 - Local file
    path = "file://%s" % os.path.abspath(input)
    return [path if os.path.exists(input) else parser_error("file could not \
be found (maybe you forgot to add http/https).")]


def send_request(url):
    '''
    Send requests with Requests
    '''
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) \
        AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36',
        'Accept': 'text/html,\
        application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
        'Accept-Language': 'en-US,en;q=0.8',
        'Accept-Encoding': 'gzip',
        'Cookie': args.cookies
    }

    requests.packages.urllib3.disable_warnings(InsecureRequestWarning)
    s = requests.Session()
    s.mount('file://', FileAdapter())
    content = s.get(url, headers=headers, timeout=1, stream=True, verify=False)
    return content.text if hasattr(content, "text") else content.content


def parser_file(content):
    '''
    Parse Input
    '''
    
    # Beautify
    if args.output != 'cli':
        content = jsbeautifier.beautify(content)
    
    items = re.findall(regex, content)
    items = list(set(items))
        
    # Match Regex
    filtered_items = []

    for item in items:
        # Remove other capture groups from regex results
        group = list(filter(None, item))

        if args.regex:
            if re.search(args.regex, group[1]):
                filtered_items.append(group)
        else:
            filtered_items.append(group)

    return filtered_items

def cli_output(endpoints,base):
    '''
    Output to CLI
    '''
    for endpoint in endpoints:
        print(cgi.escape(endpoint[1]).encode(
            'ascii', 'ignore').decode('utf8')) 
        if base and not "//" in cgi.escape(endpoint[1]).encode('ascii', 'ignore').decode('utf8'):
            try:
                print(requests.get(base+cgi.escape(endpoint[1]).encode('ascii', 'ignore').decode('utf8')).status_code)
            except:
                print("error")
def html_save(html):
    '''
    Save as HTML file and open in the browser
    '''
    hide = os.dup(1)
    os.close(1)
    os.open(os.devnull, os.O_RDWR)
    try:
        s = Template(open('%s/template.html' % sys.path[0], 'r').read())

        text_file = open(args.output, "wb")
        text_file.write(s.substitute(content=html).encode('utf8'))
        text_file.close()

        print("URL to access output: file://%s" % os.path.abspath(args.output))
        file = "file://%s" % os.path.abspath(args.output)
        if sys.platform == 'linux' or sys.platform == 'linux2':
            subprocess.call(["xdg-open", file])
        else:
            webbrowser.open(file)
    except Exception as e:
        print("Output can't be saved in %s \
            due to exception: %s" % (args.output, e))
    finally:
        os.dup2(hide, 1)

# Convert input to URLs or JS files
urls,base = parser_input(args.input)  
urls2=urls
if args.site:
    r = requests.get(urls[0])
    soup = BeautifulSoup(r.content, "lxml")
    src = [sc["src"] for sc in  soup.select("script[src]")]
    for i,url in enumerate(src):
        if urls[0].split('/')[-1] not in url and ("http" or "https" in url) :
            src.pop(i)
        if  url.split('/')[0] not in ["https:","https:"]:    
            print "&&&&&&&&"
            print url        
            urls2.append( urls[0] + url)
            print urls[0] + url
    print(src)
    print ("#########")
    urls2 = src

for i,elem in enumerate(urls2):
	if elem[:4] != "http":
		urls2[i] = base + urls2[i]

# Convert URLs to JS
html = ''
for url in urls2:
    if not args.burp:
        try:
            print url
            file = send_request(url)
        except Exception as e:
            parser_error("invalid input defined or SSL error: %s" % e)
    else: 
        file = url['js']
        url = url['url']

    endpoints = parser_file(file)

    if args.output == 'cli':
        cli_output(endpoints,base)
    else:
        html += '''
            <h1>File: <a href="%s" target="_blank" rel="nofollow noopener noreferrer">%s</a></h1>
            ''' % (cgi.escape(url), cgi.escape(url))

        for endpoint in endpoints:
            url = cgi.escape(endpoint[1])
            string = "<div><a href='%s' class='text'>%s" % (
                cgi.escape(url),
                cgi.escape(url)
            )
            string2 = "</a><div class='container'>%s</div></div>" % cgi.escape(
                endpoint[0]
            )
            string2 = string2.replace(
                cgi.escape(endpoint[1]),
                "<span style='background-color:yellow'>%s</span>" %
                cgi.escape(endpoint[1])
            )
        
            html += string + string2

if args.output != 'cli':
    html_save(html)
