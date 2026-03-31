"""分词与文本预处理模块."""

import re
from typing import List, Set, Optional

# 默认停用词表 (来自 memory/vector/tf_vectorizer.py)
DEFAULT_STOP_WORDS = {
    "i", "me", "my", "myself", "we", "our", "ours", "ourselves", "you", "your", "yours",
    "he", "him", "his", "she", "her", "hers", "it", "its", "they", "them", "their",
    "what", "which", "who", "whom", "this", "that", "these", "those", "am", "is", "are",
    "was", "were", "be", "been", "being", "have", "has", "had", "having", "do", "does",
    "did", "doing", "a", "an", "the", "and", "but", "if", "or", "because", "as", "until",
    "while", "of", "at", "by", "for", "with", "about", "against", "between", "into",
    "through", "during", "before", "after", "above", "below", "to", "from", "up", "down",
    "in", "out", "on", "off", "over", "under", "again", "further", "then", "once", "here",
    "there", "when", "where", "why", "how", "all", "any", "both", "each", "few", "more",
    "most", "other", "some", "such", "no", "nor", "not", "only", "own", "same", "so",
    "than", "too", "very", "s", "t", "can", "will", "just", "don", "should", "now"
}


def simple_stem(word: str) -> str:
    """简单词干提取：移除常见后缀."""
    if len(word) > 4:
        if word.endswith('ing'):
            return word[:-3]
        if word.endswith('ed'):
            return word[:-2]
        if word.endswith('s') and not word.endswith('ss'):
            return word[:-1]
    return word


def tokenize(text: str, 
             lower: bool = True, 
             use_stemming: bool = True, 
             remove_stop_words: bool = True,
             stop_words: Optional[Set[str]] = None) -> List[str]:
    """分词处理.
    
    Args:
        text: 输入文本
        lower: 是否转小写
        use_stemming: 是否使用词干提取
        remove_stop_words: 是否移除停用词
        stop_words: 自定义停用词集合，若为None则使用默认
        
    Returns:
        Token列表
    """
    if not text:
        return []

    if lower:
        text = text.lower()
        
    # 使用 \b\w+\b 匹配单词
    raw_tokens = re.findall(r'\b\w+\b', text)
    
    if not raw_tokens:
        return []
        
    if stop_words is None:
        stop_words = DEFAULT_STOP_WORDS
        
    tokens = []
    for t in raw_tokens:
        # 过滤单字符 (vector_db 逻辑)
        if len(t) <= 1:
            continue
            
        if remove_stop_words and t in stop_words:
            continue
            
        if use_stemming:
            t = simple_stem(t)
            
        tokens.append(t)
        
    return tokens
