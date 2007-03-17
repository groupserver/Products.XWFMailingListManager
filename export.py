def export_archive_as_mbox( archive, writer=None ):
    result = ''
    for object in archive.objectValues('Folder'):
        out = []
        headers = object.getProperty('headers')
        if headers:
            out.append(headers)
            if object.getProperty('x-xwfnotification-file-id') and headers.find('X-XWFNotification-File-Id') == -1:
                out.append('X-XWFNotification-File-Id: %s' % object.getProperty('x-xwfnotification-file-id'))
                out.append('X-XWFNotification: File')
        else:
            for item in object.propertyMap():
                propertyId = item['id']
                propertyType = item['type']
                if propertyId not in ['title', 'mailFrom', 'mailSubject', 'mailDate', 'mailBody', 'compressedSubject', 'mailUserId', 'date']:
                    if propertyType in ('lines','ulines'):
                        for line in object.getProperty(propertyId):
                            out.append(propertyId.capitalize()+': '+line)
                    else:
                        out.append(propertyId.capitalize()+': '+object.getProperty(propertyId, ''))
    
            out.append('Date: %s' % object.getProperty('mailDate').rfc822())
    
        out.append('X-GSOriginal-ID: %s' % object.getId())
        out.append('X-GSUser-Id: %s' % object.getProperty('mailUserId', ''))
        out.append('')
        
        body = object.getProperty('mailBody')
    
        out.append(body)
        
        newout = ''
        for line in out:
            try:
                newout += line.decode('utf-8')+'\n'
            except:
                try:
                    newout += line.decode('iso-8859-15')+'\n'
                except:
                    newout += line.decode('iso-8859-15', 'ignore')+'\n'
        
        mailfrom = object.getProperty('from')
        if isinstance(mailfrom, list) or isinstance(mailfrom, tuple):
            mailfrom = mailfrom[0]
        else:
            mailfrom = object.getProperty('mailFrom')
        
        result += 'From %s %s\n' % (mailfrom, object.getProperty('mailDate').rfc822())
        for line in newout.split('\n'):
            if line.find('From ') == 0:
                result += '>'+line+'\n'
            else:
                result += line+'\n'
        
        if writer:
            writer.write( str(result) )
            result = ''
            
    return result
