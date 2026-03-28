"""Seed script for PDF documents and annotations (Scandinavia POC)."""
from __future__ import annotations

import sys
import os

sys.path.insert(0, os.path.dirname(__file__))

from app.database import SessionLocal, engine, Base
from app.models import Document, DocumentAnnotation, Incentive, Treaty


def seed_documents():
    db = SessionLocal()

    # Clear existing document data
    db.query(DocumentAnnotation).delete()
    db.query(Document).delete()
    db.commit()

    # Look up incentive and treaty IDs for linking
    def incentive_id(name: str) -> int | None:
        inc = db.query(Incentive).filter(Incentive.name == name).first()
        return inc.id if inc else None

    def treaty_id(name: str) -> int | None:
        t = db.query(Treaty).filter(Treaty.name == name).first()
        return t.id if t else None

    # --- Japan JLOX+ 2026 Guidelines ---
    jp_inc_id = incentive_id("Japan JLOX+ Location Incentive Program")
    doc_jp = Document(
        title="Japan JLOX+ Location Incentive Program Guidelines (R6/2026)",
        document_type="incentive_guidelines",
        language="ja",
        country_codes=["JP"],
        filename="jp_jlox_plus_2026_guidelines.pdf",
        page_count=45,
        original_url="http://www.vipo.or.jp/u/jloxplusr6_2_youkou-1.pdf",
        publisher="Visual Industry Promotion Organization (VIPO)",
        date_downloaded="2026-03-26",
        incentive_id=jp_inc_id,
    )
    db.add(doc_jp)
    db.flush()

    jp_annotations = [
        DocumentAnnotation(
            document_id=doc_jp.id,
            page_number=5,
            search_text="50%",
            clause_reference="Subsidy Rate",
            topic="rebate_rate",
            english_summary="50% cash rebate on qualifying expenses incurred in Japan.",
            incentive_id=jp_inc_id,
            sort_order=1,
        ),
        DocumentAnnotation(
            document_id=doc_jp.id,
            page_number=10,
            search_text="1,000,000,000",
            clause_reference="Maximum Grant",
            topic="cap",
            english_summary="Maximum grant is JPY 1 billion per project.",
            incentive_id=jp_inc_id,
            sort_order=2,
        ),
    ]
    db.add_all(jp_annotations)

    # --- India Revised Incentive Guidelines 2024-2026 ---
    in_inc_id = incentive_id("India Incentive Scheme for Foreign Films and Official AV Coproductions")
    doc_in = Document(
        title="India Revised Incentive Guidelines for Foreign Films (2024-2026)",
        document_type="incentive_guidelines",
        language="en",
        country_codes=["IN"],
        filename="in_ffo_revised_guidelines_2024.pdf",
        page_count=20,
        original_url="https://mib.gov.in/sites/default/files/2024-02/Revised%20incentive%20guidelines.pdf",
        publisher="Ministry of Information and Broadcasting (India)",
        date_downloaded="2026-03-26",
        incentive_id=in_inc_id,
    )
    db.add(doc_in)
    db.flush()

    in_annotations = [
        DocumentAnnotation(
            document_id=doc_in.id,
            page_number=1,
            search_text="40%",
            clause_reference="Clause 2.3",
            topic="rebate_rate",
            english_summary="Incentive up to 40% of the Qualifying Production Expenditure (QPE) in India (30% base + bonuses).",
            incentive_id=in_inc_id,
            sort_order=1,
        ),
        DocumentAnnotation(
            document_id=doc_in.id,
            page_number=1,
            search_text="300 million",
            clause_reference="Clause 2.7",
            topic="cap",
            english_summary="Maximum payout per project is INR 300 million.",
            incentive_id=in_inc_id,
            sort_order=2,
        ),
    ]
    db.add_all(in_annotations)

    # --- Mexico 2026 Decree ---
    mx_inc_id = incentive_id("Mexico Federal Stimulus for Cinematic and Audiovisual Production (2026 Decree)")
    doc_mx = Document(
        title="Mexico Federal Stimulus Decree (February 2026)",
        document_type="legislation",
        language="es",
        country_codes=["MX"],
        filename="mx_federal_stimulus_decree_2026.pdf",
        page_count=8,
        original_url="https://www.dof.gob.mx/nota_detalle.php?codigo=5780237&fecha=16/02/2026",
        publisher="Diario Oficial de la Federación (DOF)",
        date_downloaded="2026-03-26",
        incentive_id=mx_inc_id,
    )
    db.add(doc_mx)
    db.flush()

    mx_annotations = [
        DocumentAnnotation(
            document_id=doc_mx.id,
            page_number=1,
            search_text="30%",
            clause_reference="Artículo Primero",
            topic="rebate_rate",
            english_summary="30% transferable tax credit on qualified Mexican expenditure.",
            incentive_id=mx_inc_id,
            sort_order=1,
        ),
    ]
    db.add_all(mx_annotations)

    # --- European Convention on Cinematographic Co-Production (Revised 2017) ---
    ec_treaty_id = treaty_id("European Convention on Cinematographic Co-Production (Revised, 2017)")
    doc_ec = Document(
        title="European Convention on Cinematographic Co-Production (Revised, CETS 220)",
        document_type="treaty_text",
        language="en",
        country_codes=["DK", "SE", "NO", "FI", "IS"],
        filename="european_convention_cets_220.pdf",
        page_count=12,
        original_url="https://rm.coe.int/168069309e",
        publisher="Council of Europe",
        date_downloaded="2026-03-25",
        treaty_id=ec_treaty_id,
    )
    db.add(doc_ec)
    db.flush()

    ec_annotations = [
        DocumentAnnotation(
            document_id=doc_ec.id,
            page_number=3,
            search_text="cinematographic work",
            clause_reference="Article 3",
            topic="definitions",
            english_summary="Defines 'cinematographic work' as a work of any length or medium, including fiction, animation and documentaries, intended for public exhibition.",
            treaty_id=ec_treaty_id,
            sort_order=1,
        ),
        DocumentAnnotation(
            document_id=doc_ec.id,
            page_number=4,
            search_text="the minimum contribution may not be less than 5%",
            clause_reference="Article 6(1)",
            topic="financial_share",
            english_summary="In multilateral co-productions, minimum contribution is 5% and maximum is 80% of total production cost. When minimum is less than 20%, competent authorities must approve.",
            treaty_id=ec_treaty_id,
            sort_order=2,
        ),
        DocumentAnnotation(
            document_id=doc_ec.id,
            page_number=4,
            search_text="In the case of bilateral co-production",
            clause_reference="Article 6(2)",
            topic="financial_share",
            english_summary="In bilateral co-productions, minimum contribution is 10% and maximum is 90% of total production cost.",
            treaty_id=ec_treaty_id,
            sort_order=3,
        ),
        DocumentAnnotation(
            document_id=doc_ec.id,
            page_number=11,
            search_text="15 points out of a possible total of 23",
            clause_reference="Appendix II, para 3",
            topic="cultural_test",
            english_summary="Animation works must score at least 15 out of 23 points on the cultural test to qualify as an official co-production.",
            treaty_id=ec_treaty_id,
            sort_order=4,
        ),
        DocumentAnnotation(
            document_id=doc_ec.id,
            page_number=12,
            search_text="at least 50% of the total applicable points",
            clause_reference="Appendix II, para 5",
            topic="cultural_test",
            english_summary="Documentary works must score at least 50% of total applicable points to qualify as an official co-production.",
            treaty_id=ec_treaty_id,
            sort_order=5,
        ),
    ]
    db.add_all(ec_annotations)

    # --- Norway NFI Incentive Regulations 2023 ---
    no_inc_id = incentive_id("Norway Incentive Scheme for International Film and TV")
    doc_no = Document(
        title="Norway NFI Incentive Regulations 2023",
        document_type="incentive_guidelines",
        language="en",
        country_codes=["NO"],
        filename="no_nfi_incentive_regulations_2023.pdf",
        page_count=6,
        original_url="https://cdn.craft.cloud/0df8a7fe-ef75-40cb-9e44-53aac4ffeac2/assets/uploads/documents/Maler-for-tilskuddsordningene/Regulations-on-financial-incentives-Norway-2023.pdf",
        publisher="Norwegian Film Institute",
        date_downloaded="2026-03-25",
        incentive_id=no_inc_id,
    )
    db.add(doc_no)
    db.flush()

    no_annotations = [
        DocumentAnnotation(
            document_id=doc_no.id,
            page_number=2,
            search_text="The grant may total up to 25 % of the approved production costs relating to the production in Norway",
            clause_reference="Section 9",
            topic="rebate_rate",
            english_summary="25% cash rebate on approved production costs incurred in Norway.",
            incentive_id=no_inc_id,
            sort_order=1,
        ),
        DocumentAnnotation(
            document_id=doc_no.id,
            page_number=2,
            search_text="total production budget of at least NOK 25 million for feature films",
            clause_reference="Section 7",
            topic="minimum_budget",
            english_summary="Minimum total production budget: NOK 25M for feature films. Minimum qualifying Norwegian spend: NOK 2M.",
            incentive_id=no_inc_id,
            sort_order=2,
        ),
        DocumentAnnotation(
            document_id=doc_no.id,
            page_number=2,
            search_text="The maximum grant per production is NOK 50 million",
            clause_reference="Section 10",
            topic="cap",
            english_summary="Maximum grant per production is NOK 50 million.",
            incentive_id=no_inc_id,
            sort_order=3,
        ),
        DocumentAnnotation(
            document_id=doc_no.id,
            page_number=5,
            search_text="minimum of 4 points from Part I Cultural criteria",
            clause_reference="Attachment 1",
            topic="cultural_test",
            english_summary="Cultural test: minimum 4 points from Part I (Cultural criteria) and 20 points overall out of 51 total.",
            incentive_id=no_inc_id,
            sort_order=4,
        ),
    ]
    db.add_all(no_annotations)

    # --- Iceland Film Reimbursement Act ---
    is_inc_id = incentive_id("Iceland Film Reimbursement")
    doc_is_act = Document(
        title="Iceland Film Reimbursement Act No. 43/1999",
        document_type="legislation",
        language="en",
        country_codes=["IS"],
        filename="is_film_reimbursement_act_43_1999.pdf",
        page_count=4,
        original_url="https://www.government.is/lisalib/getfile.aspx?itemid=623c52fa-3f97-11e7-9410-005056bc4d74",
        publisher="Government of Iceland",
        date_downloaded="2026-03-25",
        incentive_id=is_inc_id,
    )
    db.add(doc_is_act)
    db.flush()

    is_act_annotations = [
        DocumentAnnotation(
            document_id=doc_is_act.id,
            page_number=1,
            search_text="Temporary Reimbursements",
            clause_reference="Title",
            topic="overview",
            english_summary="Act on Temporary Reimbursements for Film Production in Iceland (No. 43, 22 March 1999, as amended).",
            incentive_id=is_inc_id,
            sort_order=1,
        ),
        DocumentAnnotation(
            document_id=doc_is_act.id,
            page_number=2,
            search_text="Applications for reimbursement of production costs",
            clause_reference="Article 3",
            topic="application",
            english_summary="Applications must be submitted to the Committee on Reimbursement before production begins in Iceland.",
            incentive_id=is_inc_id,
            sort_order=2,
        ),
    ]
    db.add_all(is_act_annotations)

    # --- Iceland Regulation on Reimbursements ---
    doc_is_reg = Document(
        title="Iceland Regulation on Film Reimbursements",
        document_type="legislation",
        language="en",
        country_codes=["IS"],
        filename="is_film_reimbursement_regulation.pdf",
        page_count=5,
        original_url="https://www.government.is/media/atvinnuvegaraduneyti-media/media/Acrobat/Regulation_on_Reimbursements.pdf",
        publisher="Government of Iceland",
        date_downloaded="2026-03-25",
        incentive_id=is_inc_id,
    )
    db.add(doc_is_reg)
    db.flush()

    is_reg_annotations = [
        DocumentAnnotation(
            document_id=doc_is_reg.id,
            page_number=1,
            search_text="Up to 20% of the production costs",
            clause_reference="Article 1",
            topic="rebate_rate",
            english_summary="Up to 20% reimbursement of production costs incurred in Iceland (note: rate was later increased to 25% by amendment — see government.is for current rate).",
            incentive_id=is_inc_id,
            sort_order=1,
        ),
    ]
    db.add_all(is_reg_annotations)

    # --- Iceland Cultural Test ---
    doc_is_ct = Document(
        title="Iceland Film Reimbursement Cultural Test",
        document_type="incentive_guidelines",
        language="en",
        country_codes=["IS"],
        filename="is_film_reimbursement_cultural_test.pdf",
        page_count=3,
        original_url="https://www.government.is/media/atvinnuvegaraduneyti-media/media/Acrobat/Filmreimbursements_Iceland_Culturaltest.pdf",
        publisher="Government of Iceland",
        date_downloaded="2026-03-25",
        incentive_id=is_inc_id,
    )
    db.add(doc_is_ct)
    db.flush()

    is_ct_annotations = [
        DocumentAnnotation(
            document_id=doc_is_ct.id,
            page_number=3,
            search_text="minimum of 4 points from the Cultural Criteria",
            clause_reference="Part III",
            topic="cultural_test",
            english_summary="Minimum 4 points from Cultural Criteria (Part I) and 23 points overall out of 46 total.",
            incentive_id=is_inc_id,
            sort_order=1,
        ),
    ]
    db.add_all(is_ct_annotations)

    # --- Finland Production Incentive Terms ---
    fi_inc_id = incentive_id("Finland Production Incentive")
    doc_fi_terms = Document(
        title="Finland Production Incentive — Funding Terms and Conditions",
        document_type="incentive_guidelines",
        language="en",
        country_codes=["FI"],
        filename="fi_production_incentive_terms.pdf",
        page_count=13,
        original_url="https://www.businessfinland.fi/globalassets/finnish-customers/01-funding/08-guidelines--terms/funding-terms/production_incentive_for_audiovisual_industry.pdf",
        publisher="Business Finland",
        date_downloaded="2026-03-25",
        incentive_id=fi_inc_id,
    )
    db.add(doc_fi_terms)
    db.flush()

    fi_terms_annotations = [
        DocumentAnnotation(
            document_id=doc_fi_terms.id,
            page_number=5,
            search_text="Feature film: 500,000",
            clause_reference="Section 7",
            topic="minimum_spend",
            english_summary="Minimum spending in Finland: EUR 500,000 for feature films, documentaries, and serial fiction/animation.",
            incentive_id=fi_inc_id,
            sort_order=1,
        ),
        DocumentAnnotation(
            document_id=doc_fi_terms.id,
            page_number=5,
            search_text="Feature film: 2,500,000",
            clause_reference="Section 7",
            topic="minimum_budget",
            english_summary="Minimum overall budget: EUR 2,500,000 for feature films, EUR 650,000 for documentaries.",
            incentive_id=fi_inc_id,
            sort_order=2,
        ),
    ]
    db.add_all(fi_terms_annotations)

    # --- Finland Government Decree ---
    doc_fi_decree = Document(
        title="Finland Government Decree on Cash Rebate for Audiovisual Productions 2024–2026",
        document_type="legislation",
        language="en",
        country_codes=["FI"],
        filename="fi_production_incentive_govt_decree.pdf",
        page_count=3,
        original_url="https://www.businessfinland.fi/globalassets/finnish-customers/01-funding/07-av-cash-rebate/kaannos_vnasetus_maksuhyvityksesta_audiovisuaalisiin_tuotantoihin_1203_2023_en.pdf",
        publisher="Government of Finland / Business Finland",
        date_downloaded="2026-03-25",
        incentive_id=fi_inc_id,
    )
    db.add(doc_fi_decree)
    db.flush()

    fi_decree_annotations = [
        DocumentAnnotation(
            document_id=doc_fi_decree.id,
            page_number=2,
            search_text="cash rebate can be paid for a maximum of 25 per cent",
            clause_reference="Section 8",
            topic="rebate_rate",
            english_summary="Cash rebate of maximum 25% of eligible production costs incurred in Finland.",
            incentive_id=fi_inc_id,
            sort_order=1,
        ),
        DocumentAnnotation(
            document_id=doc_fi_decree.id,
            page_number=2,
            search_text="Eligible costs include all costs directly incurred in Finland",
            clause_reference="Section 6",
            topic="eligible_costs",
            english_summary="Eligible costs: all costs directly incurred in Finland from production (including pre- and post-production). Must be from companies/employees liable to pay tax in Finland.",
            incentive_id=fi_inc_id,
            sort_order=2,
        ),
    ]
    db.add_all(fi_decree_annotations)

    # --- Film i Väst Regulations ---
    fiv_inc_id = incentive_id("Film i Väst (West Sweden Film Fund)")
    doc_fiv = Document(
        title="Film i Väst — Regulations for Co-production",
        document_type="regional_fund",
        language="en",
        country_codes=["SE"],
        filename="se_film_i_vast_regulations.pdf",
        page_count=7,
        original_url="https://a.storyblok.com/f/309335/x/89ea489193/film-i-vast-s-regulation-for-co-production-valid-from-240101.pdf",
        publisher="Film i Väst / Region Västra Götaland",
        date_downloaded="2026-03-25",
        incentive_id=fiv_inc_id,
    )
    db.add(doc_fiv)
    db.flush()

    fiv_annotations = [
        DocumentAnnotation(
            document_id=doc_fiv.id,
            page_number=3,
            search_text="Film i V\u00e4st is a wholly owned company within Region V\u00e4stra G\u00f6taland",
            clause_reference="Introduction",
            topic="overview",
            english_summary="Film i Väst is a regional film fund owned by Region Västra Götaland, investing in film and drama of the highest artistic quality.",
            incentive_id=fiv_inc_id,
            sort_order=1,
        ),
    ]
    db.add_all(fiv_annotations)

    # --- Film Stockholm Guidelines (Swedish) ---
    fs_inc_id = incentive_id("Film Stockholm")
    doc_fs = Document(
        title="Film Stockholm — Riktlinjer för samproduktion",
        document_type="regional_fund",
        language="sv",
        country_codes=["SE"],
        filename="se_film_stockholm_guidelines.pdf",
        page_count=8,
        original_url="https://filmstockholm.se/wp-content/uploads/2021/09/Film-Stockholm-ABs-riktlinjer-for-insatser-vid-samproduktion_20210920.pdf",
        publisher="Film Stockholm AB",
        date_downloaded="2026-03-25",
        incentive_id=fs_inc_id,
    )
    db.add(doc_fs)
    db.flush()

    fs_annotations = [
        DocumentAnnotation(
            document_id=doc_fs.id,
            page_number=1,
            search_text="riktlinjer f\u00f6r insatser vid samproduktion",
            clause_reference="Title",
            topic="overview",
            original_text="Film Stockholm AB:s riktlinjer för insatser vid samproduktion",
            english_summary="Film Stockholm AB's guidelines for co-production investments. Regional fund investing in films, TV dramas, and new formats.",
            incentive_id=fs_inc_id,
            sort_order=1,
        ),
    ]
    db.add_all(fs_annotations)

    # --- Arctic Film Norway Guidelines (Norwegian) ---
    afn_inc_id = incentive_id("Arctic Film Norway (formerly Nordnorsk Filmsenter)")
    doc_afn = Document(
        title="Arctic Film Norway — Retningslinjer for tilskudd",
        document_type="regional_fund",
        language="no",
        country_codes=["NO"],
        filename="no_arctic_film_guidelines.pdf",
        page_count=10,
        original_url="https://arktiskfilmnorge.no/wp-content/uploads/2025/06/20242712_retningslinjer_AFN.pdf",
        publisher="Arktisk Film Norge AS",
        date_downloaded="2026-03-25",
        incentive_id=afn_inc_id,
    )
    db.add(doc_afn)
    db.flush()

    afn_annotations = [
        DocumentAnnotation(
            document_id=doc_afn.id,
            page_number=1,
            search_text="Retningslinjer for tilskudd fra Arktisk Film Norge",
            clause_reference="Title",
            topic="overview",
            original_text="Retningslinjer for tilskudd fra Arktisk Film Norge AS",
            english_summary="Guidelines for grants from Arctic Film Norway. Regional fund supporting film production in Northern Norway (Tromsø, Lofoten, Arctic).",
            incentive_id=afn_inc_id,
            sort_order=1,
        ),
    ]
    db.add_all(afn_annotations)

    # --- Vestnorsk Filmsenter Regulations (Norwegian) ---
    vn_inc_id = incentive_id("Vestnorsk Filmsenter (Western Norway Film Fund)")
    doc_vn = Document(
        title="Vestnorsk Filmsenter — Regelverk",
        document_type="regional_fund",
        language="no",
        country_codes=["NO"],
        filename="no_vestnorsk_regulations.pdf",
        page_count=19,
        original_url="https://vestnorskfilm.no/images/Regelverk.pdf",
        publisher="Vestnorsk Filmsenter",
        date_downloaded="2026-03-25",
        incentive_id=vn_inc_id,
    )
    db.add(doc_vn)
    db.flush()

    vn_annotations = [
        DocumentAnnotation(
            document_id=doc_vn.id,
            page_number=1,
            search_text="Retningslinjer",
            clause_reference="Title",
            topic="overview",
            original_text="Regelverk — Vestnorsk Filmsenter",
            english_summary="Regulations for Vestnorsk Filmsenter (Western Norway Film Fund). Regional fund supporting production in the Bergen/fjord region.",
            incentive_id=vn_inc_id,
            sort_order=1,
        ),
    ]
    db.add_all(vn_annotations)

    db.commit()

    # Summary
    n_docs = db.query(Document).count()
    n_anns = db.query(DocumentAnnotation).count()
    print(f"Seeded {n_docs} documents with {n_anns} annotations.")

    db.close()


if __name__ == "__main__":
    seed_documents()
