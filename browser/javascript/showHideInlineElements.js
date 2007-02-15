function showHideInline(remainderId, discloseButtonId) 
{
    var hiddenArrow = "\u25b6";
    var shownArrow = "\u25bc";
    var discloseElement = document.getElementById(discloseButtonId);
    if (discloseElement.childNodes[0].data == shownArrow)
    { 
        discloseElement.setAttribute('title', "Show the footer");
        discloseElement.childNodes[0].data = hiddenArrow;
    }
    else
    {
        discloseElement.setAttribute('title', "Hide the footer");
        discloseElement.childNodes[0].data = shownArrow;
    }
    Effect.toggle(remainderId,'blind', {duration: 1, delay: 0});
}
