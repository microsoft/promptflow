// This is used to zoom in images when clicked on
window.onload = () => {
    if (document.getElementById("lightbox") === null){
      // Append lightbox div to each page
      let div = document.createElement('div');
      div.innerHTML = '<div id="lightbox"></div>';
      document.body.appendChild(div);
    }

    // (A) GET LIGHTBOX & ALL .ZOOMD IMAGES
    let all = document.getElementsByClassName("bd-article")[0].getElementsByTagName("img"),
        lightbox = document.getElementById("lightbox");

    // (B) CLICK TO SHOW IMAGE IN LIGHTBOX
    // * SIMPLY CLONE INTO LIGHTBOX & SHOW
    if (all.length>0) { for (let i of all) {
      i.onclick = () => {
        let clone = i.cloneNode();
        clone.className = "";
        lightbox.innerHTML = "";
        lightbox.appendChild(clone);
        lightbox.className = "show";
      };
    }}

    // (C) CLICK TO CLOSE LIGHTBOX
    lightbox.onclick = () => {
      lightbox.className = "";
    };
};

// This is used to control homepage background
if (window.location.pathname === "/" || window.location.pathname === "/index.html") {
  var observer = new MutationObserver(function(mutations) {
    const dark = document.documentElement.dataset.theme == 'dark';
    document.body.style.backgroundSize = "100%";
    document.body.style.backgroundPositionY = "bottom";
    document.body.style.backgroundRepeat = "no-repeat"
    if (dark) {
      if (window.screen.width <= 1280){
        document.body.style.backgroundImage = "url('_static/bg_dark_small.png')"
      } else {
        document.body.style.backgroundImage = "url('_static/bg_dark_large.png')"
      }
    } else {
      if (window.screen.width <= 1280){
        document.body.style.backgroundImage = "url('_static/bg_light_small.png')"
      } else {
        document.body.style.backgroundImage = "url('_static/bg_light_large.png')"
      }
    }
  })
  observer.observe(document.documentElement, {attributes: true, attributeFilter: ['data-theme']});
}
