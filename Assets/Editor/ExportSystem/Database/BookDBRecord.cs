using SQLite;

namespace Database
{
    [Table("Books")]
    public class BookDBRecord
    {
        [PrimaryKey]
        public string BookName { get; set; }
        public string PageContent { get; set; }
    }
}
