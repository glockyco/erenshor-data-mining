using SQLite;

namespace Database
{
    [Table("Books")]
    public class BookDBRecord
    {
        public string BookTitle { get; set; }
        public int PageNumber { get; set; }
        public string PageContent { get; set; }
    }
}
