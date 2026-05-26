// version: 7.12.0.a.1.5.0
// sha: 762cd4305282c6e9a675329d2c5b8624a225ecdd
function SetBookmark(){var o=window.parent,t=window.location.href;o.SetBookmark(t.substring(t.toLowerCase().lastIndexOf("/scormcontent/")+14,t.length),document.title),o.CommitData()}SetBookmark();