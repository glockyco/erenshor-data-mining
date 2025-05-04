using SQLite;

namespace Database
{
    [Table("Books")]
    public class BookDBRecord
    {
        [PrimaryKey]
        public string BookTitle { get; set; }
        [PrimaryKey]
        public int PageNumber { get; set; }
        public string PageContent { get; set; }
    }
}
