def crop_email(text, lines=0, max_consecutive_comment=12, max_consecutive_whitespace=3):
    slines = text.split('\n')
    
    intro = []; body = []; i = 1; bodystart = 0; consecutive_comment = 0; consecutive_whitespace = 0
    for line in slines:
        if (line[:2] == '--' or line[:2] == '==' or line[:2] == '__' or
            line[:2] == '~~' or line [:3] == '- -'):
            bodystart = 1
    
        if bodystart: # if we've started on the body, just append to body
            body.append(line)
        elif consecutive_comment >= max_consecutive_comment and i > 25: # count comments, but don't penalise top quoting as badly
            body.append(line)
            bodystart = 1
        elif (i <= 15): # if we've got less than 15 lines, just put it in the intro
            intro.append(line)
        elif (len(line) > 3 and line[:4] != '>'):
            intro.append(line)
        elif consecutive_whitespace <= max_consecutive_whitespace:
            intro.append(line)
        else:
            body.append(line)
            bodystart = 1
    
        if len(line) > 3 and (line[:4] == '<' or line.lower().find('wrote:') != -1):
            consecutive_comment += 1
        else:
            consecutive_comment = 0
    
        if len(line.strip()):
            consecutive_whitespace = 0
        else:
            consecutive_whitespace += 1
    
        i += 1

    rintro = []; trim = 1
    for line in intro[::-1]:
        if len(intro) < 5:
            trim = 0
        if len(line) > 3:
            ls = line[:4]
        elif line.strip():
            ls = line.strip()[0]
        else:
            ls = ''
    
        if trim and (ls == '>' or ls == ''):
            body.insert(0, line)
        elif trim and line.find('wrote:') > 2:
            body.insert(0, line)
        elif trim and line.strip() and len(line.strip().split()) == 1:
            body.insert(0, line)
        else:
            trim = 0
            rintro.insert(0, line)

    intro = '\n'.join(rintro)
    body = '\n'.join(body)

    return intro, body

