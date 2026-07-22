# 🎧 Model Card: Music Recommender Simulation

## 1. Model Name  

**SongFit 1.0**

---

## 2. Intended Use  

The model takes one listener's stated taste and returns the top 5 songs from a small catalog, with a reason for each one.

It assumes the listener knows their own taste and can describe it in four words or numbers: a favorite genre, a favorite mood, a target energy level, and whether they like acoustic music. It also assumes they are honest about it, because there is no feedback to correct them later.

This is for classroom exploration, not for real users. The catalog is 10 or 40 songs depending on which file is loaded, and the weights were chosen by hand, not learned from anyone's listening history.

---

## 3. How the Model Works  

Every song gets points on four things, and the points are added up.

- **Genre.** Full points for the same genre. Half points if the labels share a word, so `indie pop` still counts for a pop fan.
- **Mood.** Full points for the same mood. Partial points for moods in the same family, because `chill`, `relaxed`, and `focused` mean nearly the same thing in this catalog.
- **Energy.** Full points when the song's energy matches the target. The points fade smoothly as the gap grows, so being a little off costs almost nothing.
- **Acoustic texture.** This is the only one that can subtract points. If the listener dislikes acoustic music, acoustic songs are pushed down instead of just ignored.

Genre is the heaviest at 2.0, then mood and energy at 1.5, then acoustic at 0.75. A perfect song scores 5.75. After scoring, the songs are sorted from high to low, ties are broken by song id so the output never changes between runs, and the top 5 are shown.

The starter code did not score anything. It returned the first 5 songs in the file, and the starter test still passed because the correct answer happened to be listed first. I replaced that with real scoring, added a tie-break so the results are stable, and made the explanations come from the same numbers that produced the score, so an explanation cannot disagree with the ranking. I also made the scorer a swappable object, which let me compare different models without editing the recommender.

---

## 4. Data  

There are two catalogs. Both use the same columns: genre, mood, energy, tempo, valence, danceability, and acousticness.

- `data/songs.csv` is the original 10 songs from the starter. Genres are pop, lofi, rock, ambient, jazz, synthwave, and indie pop. Moods are happy, chill, intense, relaxed, moody, and focused.
- `data/songs_extended.csv` is 40 songs. I kept the original 10 and added 30 more.

I added the extra songs because the original 10 could not test much. Asking for 5 songs out of 10 returns half the catalog, and four of the genres had exactly one song each.

The bigger problem was that the original catalog has no sad music at all. The lowest valence is 0.48 and no song is tagged `sad`. So I added 8 low-valence songs, a near-duplicate pair by different artists, a fourth track for one artist, two songs at the extreme ends of the energy scale, and one new genre.

A lot of musical taste is still missing. There is no hip hop, classical, metal, country, or anything not sung in English. The model does not know lyrics, language, era, or whether a song is live or studio. It also does not know which songs are popular.

---

## 5. Strengths  

It works well for listeners whose favorite genre is well represented. Pop has 7 songs and lofi has 8, and both of those profiles get sensible results.

The mood family rule works better than I expected. For the lofi study profile, ranks 2 and 3 are songs tagged `chill` rather than `focused`, and they are genuinely good picks that an exact-match rule would have scored as zero.

The explanations are the part I trust most. Because the score is a sum, each feature's share of the total is exact, so the reasons shown are really the reasons the song won. The explanation also mentions the song's weakest point instead of only listing good news.

The results are also fully repeatable. Shuffling the catalog does not change the output, which I confirmed with a test.

---

## 6. Limitations and Bias 

- The model uses only 4 of the 7 features. Valence, tempo, and danceability are loaded but never scored in the main model.
- Because valence is unused, sadness is only skin-deep. Two songs both tagged `sad` score the same even if one has valence 0.05 and the other 0.44.
- Genre matching splits on spaces, so a hyphenated genre like `post-rock` scores zero against `rock`. Any genre written with punctuation is invisible to a fan of its parent genre.
- The mood families are my own judgment. I decided `focused` belongs with `chill` and `relaxed`. A listener whose focus music is fast and loud is mis-served by design and has no way to say so.
- Listeners in thin genres get worse and less stable results. Folk and indie have 2 songs each, and small weight changes move their results much more than a pop fan's.
- Near-duplicates crowd the top. For the melancholy profile, ranks 1 and 2 are two songs I deliberately made almost identical. Each is a good pick on its own, but together they waste a slot.
- The system always returns 5 songs, even when only 3 fit. On the original 10-song catalog, ranks 4 and 5 for the pop profile score 1.96 and 1.89 against a top score of 5.48, but they are displayed in the same format as a strong match.
- The acoustic term is stronger than it looks. Its swing from worst to best is 1.5 points, which is the same as a full mood match, so ticking that box can quietly override a mood preference.
- Nothing is learned. The same listener sees the same 5 songs forever, and the model never finds out it was wrong.

---

## 7. Evaluation  

I tested five profiles: pop-happy, lofi-study, melancholy, jazz-relaxed, and one I called sad-but-not-bleak. I mainly checked whether the top results made sense to me and whether the stated reasons matched the songs. I also wrote 39 tests, most of them checking rules that should hold for any sensible scoring model, such as that shuffling the input does not change the output and that moving a song's energy toward the target never lowers its score.

Two results surprised me.

First, changing the genre weight from 2.0 to 0.5 did not change the top 5 at all for the pop, lofi, and melancholy profiles. It only reordered the jazz fan's results. The reason is that in this catalog the pop songs are also the happy, high-energy ones, so genre is partly redundant. I expected genre to dominate everything because it has the highest weight, but a song with the right mood and energy and the wrong genre scores 3.00, which beats a song with the right genre and nothing else at 2.08.

Second, I built a separate 6-feature model that adds valence and tempo, and compared it against the original. For most profiles it changed nothing. But for the sad-but-not-bleak profile it replaced 3 of the 5 results. The original model had recommended a song called `Confetti Kids` at rank 3, which is tagged `happy` with valence 0.88, to a listener who asked for sad music. It did that because only 2 pop songs are tagged `sad`, so the genre weight filled the rest of the list with any pop song. That is the clearest example of the bias I listed above.

---

## 8. Future Work  

- Use valence and danceability in the main model, since they are already in the data.
- Fix the genre matching so hyphenated genres are split properly.
- Stop returning 5 songs no matter what. A minimum score would be more honest than filling the list.
- Add a diversity rule so two near-identical songs cannot both sit at the top.
- Let the listener set their own weights, instead of me deciding that genre matters most.
- Show more than 3 reasons per song. Right now valence and tempo can change the ranking without ever appearing in the explanation.
- Try collaborative filtering. That would need a completely different dataset with several users and their listening history, which this project does not have.

---

## 9. Personal Reflection  

I learned some technical terms like feature contribution and content-based recommendation. I already knew how similarity measures work, but seeing them in practice opened my mind to their limitations as well as their advantages.

Ideally I would prefer to compare several methods, but the data is too small to support that kind of optimization. Collaborative filtering, for example, is impossible here because the dataset has no other users to learn from.