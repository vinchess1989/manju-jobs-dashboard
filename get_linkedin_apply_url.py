import urllib.request
import re

html = urllib.request.urlopen("https://fi.linkedin.com/jobs/view/content-editor-remote-at-yo-it-consulting-4423896008").read().decode("utf-8")
matches = re.findall(r'"applyUrl":"([^"]+)"', html)
for m in set(matches):
    print("Found applyUrl:", m)
