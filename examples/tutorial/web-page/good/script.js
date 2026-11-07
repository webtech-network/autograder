document.getElementById("add").addEventListener("click", () => {
  const book = document.createElement("article");
  book.className = "book";
  book.textContent = "New book";
  document.querySelector(".books").appendChild(book);
});
