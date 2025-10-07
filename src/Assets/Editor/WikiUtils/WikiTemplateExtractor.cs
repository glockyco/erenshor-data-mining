using System;
using System.Collections.Generic;

public class WikiTemplateExtractor
{
    public static List<string> ExtractTemplates(string text, string templateName)
    {
        var results = new List<string>();
        string startTag = "{{" + templateName;
        int idx = 0;

        while ((idx = text.IndexOf(startTag, idx, StringComparison.Ordinal)) != -1)
        {
            int start = idx;
            int braceLevel = 2; // for the initial {{
            idx += startTag.Length;

            while (idx < text.Length)
            {
                if (text.Substring(idx).StartsWith("{{"))
                {
                    braceLevel += 2;
                    idx += 2;
                }
                else if (text.Substring(idx).StartsWith("}}"))
                {
                    braceLevel -= 2;
                    idx += 2;
                    if (braceLevel == 0)
                    {
                        results.Add(text.Substring(start, idx - start));
                        break;
                    }
                }
                else
                {
                    idx++;
                }
            }
        }

        return results;
    }
}