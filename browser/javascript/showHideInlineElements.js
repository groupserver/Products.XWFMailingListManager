function showHideInline(remainderId, discloseButtonId) 
{
    var i=0;
    var remainderElement = document.getElementById(remainderId);
    var discloseElement = document.getElementById(discloseButtonId);
    var img = discloseElement.childNodes[1];
    const hiddenArrow = "\u25b6";
    const shownArrow = "\u25bc"
    
    if (remainderElement.getAttribute('class') == 'emailRemainderShown')
    { 
        remainderElement.setAttribute('class', 'emailRemainderHidden');
        discloseElement.setAttribute('title', 
                                      "Show the email footer");
        img.setAttribute("src",
                         '/++resource++postImages/disclosure-arrow-hidden.gif');
    }
    else
    {
        remainderElement.setAttribute('class', 'emailRemainderShown');
        discloseElement.setAttribute('title', 
                                      "Hide the email footer");
        img.setAttribute("src",
                         '/++resource++postImages/disclosure-arrow-shown.gif');
    }
}
