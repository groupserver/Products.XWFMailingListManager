import urllib, re, sys

outdir = "archives/"
url = 'http://lists.ourshack.com/pipermail/mythtvnz'
page = urllib.urlopen(url)
text = page.read()

sys.stdout.write(('%s\n' % text))
matcher = re.compile('href=\"(.*\.gz)\"')

matches = matcher.findall(text)

for match in matches:
    fileurl = url+'/'+match
    remotefile = urllib.urlopen(fileurl)
    
    outfile = file(outdir+'/'+match, 'w+')
    outfile.write(remotefile.read())
    outfile.close()
