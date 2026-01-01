"""
Sequence alignment: ASR word listesi ile hedef Kuran metni arasında DP alignment
Needleman-Wunsch benzeri algoritma
"""

from typing import List, Dict, Tuple, Optional
from rapidfuzz import fuzz
from utils.arabic_norm import normalize_ar
import numpy as np

def align_words(
    rec_words: List[Dict], 
    tgt_words: List[Dict]
) -> List[Tuple[Optional[int], Optional[int]]]:
    """
    ASR kelimeleri ile hedef kelimeleri hizalar (DP alignment)
    
    Args:
        rec_words: [{w: str, start_ms: float, end_ms: float}] - ASR çıktısı
        tgt_words: [{w: str, ayah_idx: int}] - Hedef Kuran kelimeleri
    
    Returns:
        pairs: List of tuples (i_rec or None, i_tgt or None)
        Her tuple bir eşleşmeyi temsil eder:
        - (i_rec, i_tgt): Eşleşme
        - (i_rec, None): Insertion (ASR'de var, hedefte yok)
        - (None, i_tgt): Deletion (Hedefte var, ASR'de yok)
    """
    n_rec = len(rec_words)
    n_tgt = len(tgt_words)
    
    if n_rec == 0 and n_tgt == 0:
        return []
    
    # Normalize kelimeleri önceden hesapla
    rec_norm = [normalize_ar(w.get("w", "")) for w in rec_words]
    tgt_norm = [normalize_ar(w.get("w", "")) for w in tgt_words]
    
    # DP tablosu: dp[i][j] = rec[0:i] ve tgt[0:j] arasındaki minimum cost
    # Backtrack için: prev[i][j] = (prev_i, prev_j, operation)
    dp = np.full((n_rec + 1, n_tgt + 1), float('inf'))
    prev = [[None] * (n_tgt + 1) for _ in range(n_rec + 1)]
    
    # Base case: boş stringler
    dp[0][0] = 0
    
    # İlk satır: sadece deletions
    for j in range(1, n_tgt + 1):
        dp[0][j] = dp[0][j-1] + 1  # deletion cost = 1
        prev[0][j] = (0, j-1, 'del')
    
    # İlk sütun: sadece insertions
    for i in range(1, n_rec + 1):
        dp[i][0] = dp[i-1][0] + 1  # insertion cost = 1
        prev[i][0] = (i-1, 0, 'ins')
    
    # DP doldur
    for i in range(1, n_rec + 1):
        for j in range(1, n_tgt + 1):
            rec_w = rec_norm[i-1]
            tgt_w = tgt_norm[j-1]
            
            # Substitution cost hesapla
            if rec_w == tgt_w:
                sub_cost = 0
            else:
                # Benzerlik skoru
                similarity = fuzz.ratio(rec_w, tgt_w)
                if similarity >= 85:
                    sub_cost = 0.3  # Küçük ceza
                else:
                    sub_cost = 1.0  # Tam ceza
            
            # Üç seçenek: substitution, insertion, deletion
            costs = [
                (dp[i-1][j-1] + sub_cost, (i-1, j-1, 'sub')),
                (dp[i-1][j] + 1, (i-1, j, 'ins')),  # insertion
                (dp[i][j-1] + 1, (i, j-1, 'del'))   # deletion
            ]
            
            min_cost, (prev_i, prev_j, op) = min(costs, key=lambda x: x[0])
            dp[i][j] = min_cost
            prev[i][j] = (prev_i, prev_j, op)
    
    # Backtrack: alignment çıkar
    pairs = []
    i, j = n_rec, n_tgt
    
    while i > 0 or j > 0:
        if prev[i][j] is None:
            break
        
        prev_i, prev_j, op = prev[i][j]
        
        if op == 'sub':
            pairs.append((i-1, j-1))
            i, j = prev_i, prev_j
        elif op == 'ins':
            pairs.append((i-1, None))
            i, j = prev_i, prev_j
        elif op == 'del':
            pairs.append((None, j-1))
            i, j = prev_i, prev_j
    
    # Pairs'ı ters çevir (baştan sona sıralı olması için)
    pairs.reverse()
    
    return pairs

