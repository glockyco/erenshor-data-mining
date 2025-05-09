using SQLite;

namespace Database
{
    [Table("Books")]
    public class BookDBRecord
    {
        [Indexed(Name = "Books_Primary_IDX", Order = 1, Unique = true)]
        public string BookTitle { get; set; }
        [Indexed(Name = "Books_Primary_IDX", Order = 2, Unique = true)]
        public int PageNumber { get; set; }
        public string PageContent { get; set; }
    }
}
