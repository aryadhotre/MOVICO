"""MOVICO recommendation engine.

The engine is deliberately split so each stage can be trained, evaluated and
swapped independently:

    dataset   -> interaction artifacts built from the MovieLens archive
    ials      -> conjugate-gradient implicit ALS (latent collaborative signal)
    itemknn   -> pruned item-item cosine neighbourhood (explanations, similars)
    content   -> multi-channel content embeddings (cold start, novelty)
    ranker    -> fold-in + score fusion + diversity/novelty re-ranking
    evaluate  -> strong-generalisation ranking metrics
"""
