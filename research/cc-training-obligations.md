# What CC BY and CC BY-SA training text requires of a released model and dataset

**Retrieval date:** 2026-10-22
**Scope:** [Check what CC BY and BY-SA training text requires of a released model and dataset](https://github.com/neoyipeng2018/nlp-wayfinder/issues/160) (map [#157](https://github.com/neoyipeng2018/nlp-wayfinder/issues/157)). The setup is a Qwen3 classifier with an Apache-2.0 base. It is fine-tuned on news passages under CC BY 4.0 (VOA MOT collection and several Common Pile News publishers), CC BY 3.0, CC BY-SA 4.0 (Oxpeckers and The Public Record), and public-domain VOA text.
**Sources:** These are Creative Commons primary sources only:
- [CC BY-SA 4.0 legal code](https://creativecommons.org/licenses/by-sa/4.0/legalcode.en). CC BY 4.0 uses the same text, minus §3(b).
- [CC BY 3.0 legal code](https://creativecommons.org/licenses/by/3.0/legalcode.en)
- [CC FAQ](https://creativecommons.org/faq/)
- CC's primer [Using CC-Licensed Works for AI Training](https://creativecommons.org/using-cc-licensed-works-for-ai-training-2/) and the [detailed legal analysis PDF (2025)](https://creativecommons.org/wp-content/uploads/2025/05/Using-CC-licensed-Works-for-AI-Training.pdf)

This memo is not legal advice.

## Bottom line

| Release | Strictly required by the licence text | CC's conservative "overcompliance" guidance | Settled? |
|---|---|---|---|
| **(a) Weights** | Nothing, unless the weights legally contain or adapt the protected expression. The licences bind only acts that need copyright permission (§8(a)). A 4-class classifier is very unlikely to hold memorised passages. | Attribution can be "a simple link to the source of the dataset". If the training data includes SA text, the model "should be made available under the same CC license", which is CC BY-SA 4.0. | **Uncertain.** CC itself does not say whether weights are Adapted Material. |
| **(b) Row dataset with text and labels** | Each passage is Shared Licensed Material, so the §3(a) attribution conditions apply to every row. Each SA row stays under BY-SA. You may not impose terms that restrict the CC rights in the rows. Excerpting or truncating counts as modification and must be indicated. | The same. | **Settled.** This is ordinary redistribution. |
| **(c) Model card** | Nothing is strictly required for weights alone (see (a)). | List each source, its licence and link, and note that the text was modified or excerpted. | Cheap to do. Recommended in all cases. |

**Practical gist:** Attribute every source in the model card and in each dataset row. Ship any dataset rows with text under their per-row CC licences. Either release the weights under CC BY-SA 4.0, or exclude the two BY-SA publishers from the released model's training data, if you want to be safe under CC's conservative reading. The licence text alone probably does not force SA onto a classifier's weights, but CC has not ruled that out.

## 1. When the licence conditions bite at all

- The licence does not reach uses that need no permission. In the BY-SA 4.0 legal code, §8(a) says: "this Public License does not, and shall not be interpreted to, reduce, limit, restrict, or impose conditions on any use of the Licensed Material that could lawfully be made without permission under this Public License."
- The AI primer says: "CC licenses apply only when copyright permission is required. If exceptions or limitations apply, then the CC license terms don't apply."
- The conditions trigger on public sharing, not on training. The PDF says: "The attribution (BY) condition, the ShareAlike (SA) condition, and the NoDerivatives (ND) restriction are all triggered only upon public sharing of the original work or an adaptation of it." So private training and evaluation trigger no BY or SA obligation. Only the release does.
- Whether training itself needs permission depends on the jurisdiction. The PDF notes that Japan has an exception, the EU has an exception "except in cases where the rightsholder … has expressly opted out", and the UK and Australia have narrow exceptions. The FAQ says "as a general matter text and data mining in the United States is considered a fair use", so TDM users "do not have to adhere to the marking and attribution requirements … even though we strongly recommend they do so anyway."

## 2. (a) Released weights: are they "Adapted Material"? Does SA reach them?

- **Definition.** Under BY-SA 4.0 §1(a), Adapted Material is material "derived from or based upon the Licensed Material and in which the Licensed Material is translated, altered, arranged, transformed, or otherwise modified **in a manner requiring permission** under the Copyright and Similar Rights held by the Licensor." So the test is what copyright law says, not what the licence says.
- **The FAQ confirms that copyright law decides.** It says: "Whether a modification … is considered an adaptation … depends primarily on the applicable copyright law … Generally, a modification rises to the level of an adaptation under copyright law when the modified work is based on the prior work but manifests sufficient new creativity to be copyrightable."
- **The SA condition only applies to shared adaptations.** §3(b) says: "if You Share Adapted Material You produce … The Adapter's License You apply must be a Creative Commons license with the same License Elements, this version or later, or a BY-SA Compatible License."
- **CC's own view on models.** The PDF on ND says: "in many cases, neither the AI model nor its outputs would be considered to be derivative works of training data under copyright law." The PDF also says attribution becomes legally required "when the model memorizes and thus stores a copy of expression that is substantially similar to the CC-licensed work … as sharing the model or sharing substantially similar outputs would thus constitute sharing the work."
- **CC's conservative guidance anyway.** The PDF says: "When training data is subject to the ShareAlike condition, model outputs and the model itself, if shared publicly, should be made available under the same CC license as the original works when taking this conservative approach". It also calls this approach "almost certainly lead[ing] to overcompliance."

**Settled:** The licence does not stop you training. SA applies only if the weights are legally an adaptation and are shared.

**Uncertain:** Whether fine-tuned weights are an adaptation under any given law. CC says only "in many cases" they are not. Litigation is "ongoing" (PDF), and CC has issued no definitive ruling. A sequence classifier with a 4-way head is a weak candidate for memorising long passages, which lowers the risk. That point is our inference, not a CC statement.

**Interaction with Apache-2.0 (our inference).** Suppose you choose to release the fine-tuned weights under BY-SA 4.0. The Adapter's License covers "Your contributions" (§1(b)). Apache-2.0 still governs the Qwen base and keeps its NOTICE and attribution duties. Apache-2.0 allows your modifications to be released under other terms, so the two licences can coexist. SA licensing would, however, stop you adding restrictive terms such as non-commercial or research-only (§3(b), last sentence).

## 3. (b) Released row dataset (text + labels)

- **Shipping the passage text means Sharing the Licensed Material.** §3(a)(1) requires you to retain, where the licensor supplied them:
  - identification of the creator(s) and anyone designated for attribution
  - a copyright notice
  - a notice referring to the licence
  - a notice referring to the disclaimer
  - a URI or link "to the extent reasonably practicable"

  You must also "indicate if You modified the Licensed Material" and "indicate the Licensed Material is licensed under this Public License" with the licence text or a link.
- **"Any reasonable manner."** §3(a)(2) says "it may be reasonable to satisfy the conditions by providing a URI or hyperlink to a resource that includes the required information." On datasets the FAQ says the attribution may be "as simple as providing a link to the website where the relevant attribution information is provided." In practice, give each row `source_url`, `publisher`, `author` if supplied, `license`, and a `modified` flag (excerpted or truncated), or link a per-source attribution table.
- **Licensors can ask for removal.** Under §3(a)(3), a licensor can ask you to remove their attribution information.
- **BY-SA rows: per-row SA, not whole-dataset SA.** The FAQ says: "CC licenses do not require the collection or the compilation itself to be made available under an SA license, even though each individual work is still licensed individually under an SA license and if they were modified by the distributor the modified photo would need to be licensed under the same terms." BY 3.0 §1(b) and §4(a) say the same for "Collections".
  - So the labels and the dataset as a whole can carry a different licence, such as CC BY 4.0, while the Oxpeckers and The Public Record rows stay CC BY-SA 4.0.
  - If you excerpt or chunk a passage, mark it as modified. A plain excerpt is probably not a copyright "adaptation", because it adds no new creativity (FAQ test). Even if it were, the obligation would be to keep that row under BY-SA, which you are doing anyway.
- **No downstream restrictions.** Under §2(a)(5)(C), you "may not offer or impose any additional or different terms or conditions on … the Licensed Material if doing so restricts exercise of the Licensed Rights by any recipient." So you cannot wrap CC rows in a non-commercial or research-only dataset licence.
- **The labels are our own work.** They are not the licensor's material, so you choose their licence.
- **EU sui generis database right edge case.** §4 says: if "You include all or a substantial portion of the database contents in a database in which You have Sui Generis Database Rights, then the database … (but not its individual contents) is Adapted Material, including for purposes of Section 3(b)." This applies only where EU-style database rights exist and a substantial part of one publisher's database is taken. Oxpeckers is South African and The Public Record is American, so this is unlikely to apply. Still, this is the one path where the licence text itself forces SA onto the dataset as a whole.
- **CC BY 3.0 rows.** §4(b) requires, "reasonable to the medium or means":
  - the Original Author's name, or the designated Attribution Parties
  - the title of the Work, if supplied
  - the URI the licensor specifies, where reasonably practicable
  - "a copy of, or the Uniform Resource Identifier (URI) for, this License"

  §4(a) says this applies to the Work "as incorporated in a Collection, but this does not require the Collection apart from the Work itself to be made subject to the terms of this License." Collect the title for 3.0 rows, because 3.0 asks for it explicitly and 4.0 does not.
- **Public-domain VOA rows** carry no licence obligations. A source note is courtesy.

## 4. (c) Model card attribution

- **CC's guidance.** The PDF says: "When it comes to model training generally, attribution could be a simple link to the source of the dataset used to train the model. For example, 'Training data from the LAION dataset [link].'"
- **Recommended card section.** For each source, list the publisher, the licence with a link (CC BY 4.0, CC BY 3.0, CC BY-SA 4.0, or public domain), a link to the source or collection, a statement that the text was excerpted and labelled (modified), and a passage count. If a row dataset is also released, link to it, because its per-row attribution carries the detail.
- **Inherited notices.** State the Apache-2.0 Qwen3 base and keep its notices.
- **If you take the conservative SA route,** state that the weights are released under CC BY-SA 4.0 because the training data includes BY-SA sources. Otherwise, state the licence you chose and that the training text remains under its original licences.

## Open questions this memo cannot settle

1. Whether fine-tuned classifier weights are an "adaptation" of the training text under the relevant law (US, Singapore, or EU). CC declines to say and calls this unresolved ("litigation … remains ongoing").
2. Whether fair use or TDM exceptions cover the training in the jurisdiction where it actually happens. If they do, §8(a) removes the licence conditions for training, but not for redistributing the text in a dataset.
3. How the publishers want to be credited. §3(a)(1)(A)(i) says "in any reasonable manner requested by the Licensor", so check each publisher's reuse page.
