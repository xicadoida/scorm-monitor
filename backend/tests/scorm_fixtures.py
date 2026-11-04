SCORM12 = '''<?xml version="1.0"?>
<manifest identifier="manifest" xmlns="http://www.imsproject.org/xsd/imscp_rootv1p1p2"
 xmlns:adlcp="http://www.adlnet.org/xsd/adlcp_rootv1p2">
 <metadata><schema>ADL SCORM</schema><schemaversion>1.2</schemaversion></metadata>
 <organizations default="org"><organization identifier="org"><title>Teste</title>
 <item identifier="item" identifierref="sco"><title>Teste</title></item>
 </organization></organizations>
 <resources><resource identifier="sco" type="webcontent" adlcp:scormtype="sco" href="scormdriver/indexAPI.html">
 <file href="scormdriver/indexAPI.html"/></resource></resources>
</manifest>'''

SCORM2004 = SCORM12.replace('http://www.imsproject.org/xsd/imscp_rootv1p1p2', 'http://www.imsglobal.org/xsd/imscp_v1p1').replace('http://www.adlnet.org/xsd/adlcp_rootv1p2', 'http://www.adlnet.org/xsd/adlcp_v1p3').replace('scormtype', 'scormType').replace('<schemaversion>1.2', '<schemaversion>2004 4th Edition')
