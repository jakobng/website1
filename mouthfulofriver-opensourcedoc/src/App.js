import React, { useState, useEffect } from 'react';
import { supabase } from './supabaseClient';

// --- CONFIGURATION ---
const phaseConfig = {
  'Research & Development': { id: 'rnd', budget: '25%', color: '#7dd3c0' },
  'Production': { id: 'production', budget: '30%', color: '#5fb8a8' },
  'Post-Production': { id: 'post', budget: '30%', color: '#3d9d8a' },
  'Distribution': { id: 'dist', budget: '15%', color: '#c4a77d' },
};

const typeIcons = {
  'Footage': '🎞️',
  'Sound': '🎧',
  'Research': '📚',
  'Research + Footage': '🎞️',
  'Sound + Research': '🎧',
  'Interview': '🎤',
  'Edit': '✂️',
  'Writing': '✍️',
  'Distribution': '📡',
};

// --- STYLES (Light Theme) ---
const colors = {
  bg: '#F8F7F2',
  text: '#222',
  textLight: '#666',
  accent: '#FDB813', // The yellow/gold from your design
  accentBlue: '#00A8E8',
  border: '#222',
  borderLight: '#ddd',
};

const styles = {
  container: { minHeight: '100vh', background: colors.bg, color: colors.text, fontFamily: "'Manrope', sans-serif" },
  header: { padding: '1.25rem 2rem', borderBottom: `2px solid ${colors.border}`, position: 'sticky', top: 0, background: colors.bg, zIndex: 50 },
  navBtn: (active) => ({
    background: 'none', border: 'none',
    color: active ? colors.text : colors.textLight,
    fontSize: '0.9rem', cursor: 'pointer', padding: '0.4rem 0',
    fontWeight: active ? 700 : 400,
    borderBottom: active ? `2px solid ${colors.accent}` : '2px solid transparent',
  }),
  phaseHeader: (expanded) => ({
    width: '100%', display: 'flex', alignItems: 'center', gap: '0.75rem',
    padding: '0.75rem 1rem', background: colors.bg,
    border: `2px solid ${colors.border}`,
    cursor: 'pointer', textAlign: 'left',
    marginBottom: expanded ? 0 : '1rem',
  }),
  moduleCard: (locked) => ({
    display: 'flex', gap: '1rem', alignItems: 'flex-start',
    padding: '0.75rem',
    background: locked ? '#f0f0f0' : colors.bg,
    border: `1px solid ${colors.borderLight}`,
    cursor: locked ? 'default' : 'pointer',
    opacity: locked ? 0.6 : 1,
  }),
  btnPrimary: {
    padding: '0.75rem 1.5rem', background: colors.accent, border: 'none',
    color: colors.text, fontSize: '0.95rem', fontWeight: 700, cursor: 'pointer',
    width: '100%'
  }
};

export default function App() {
  // --- STATE ---
  const [session, setSession] = useState(null);
  const [profile, setProfile] = useState(null);
  const [modules, setModules] = useState([]);
  const [contributors, setContributors] = useState([]);
  const [submissions, setSubmissions] = useState([]);
  const [loading, setLoading] = useState(true);

  const [view, setView] = useState('about');
  const [selectedModule, setSelectedModule] = useState(null);
  const [expandedPhases, setExpandedPhases] = useState(['Research & Development']);
  const [submissionStep, setSubmissionStep] = useState(0);
  const [submissionData, setSubmissionData] = useState({ description: '', fileLinks: '' });
  const [showSuccess, setShowSuccess] = useState(false);

  // --- INITIALIZATION ---
  useEffect(() => {
    // 1. Get User Session
    supabase.auth.getSession().then(({ data: { session } }) => {
      setSession(session);
      if (session) fetchProfile(session.user.id);
    });

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      setSession(session);
      if (session) fetchProfile(session.user.id);
      else setProfile(null);
    });

    // 2. Fetch Data
    fetchData();

    return () => subscription.unsubscribe();
  }, []);

  async function fetchData() {
    const { data: modData } = await supabase.from('modules').select('*').order('created_at');
    const { data: profData } = await supabase.from('profiles').select('*').gt('stake', 0).order('stake', { ascending: false });
    const { data: subData } = await supabase.from('submissions').select(`*, module:modules(*), user:profiles(*), votes(*)`).order('created_at', { ascending: false });

    setModules(modData || []);
    setContributors(profData || []);
    setSubmissions(subData || []);
    setLoading(false);
  }

  async function fetchProfile(userId) {
    const { data } = await supabase.from('profiles').select('*').eq('id', userId).single();
    setProfile(data);
  }

  // --- ACTIONS ---
  async function signInWithGoogle() {
    await supabase.auth.signInWithOAuth({
      provider: 'google',
      options: { redirectTo: 'https://jakobng.github.io/website1/mouthfulofriver-opensourcedoc', }
    });
  }

  async function signOut() {
    await supabase.auth.signOut();
    setSession(null);
    setProfile(null);
  }

  async function submitContribution() {
    if (!session || !selectedModule) return;

    // Calculate 14 days from now
    const closeDate = new Date();
    closeDate.setDate(closeDate.getDate() + 14);

    const { error } = await supabase.from('submissions').insert({
      module_id: selectedModule.id,
      user_id: session.user.id,
      title: `Contribution: ${selectedModule.title}`,
      description: submissionData.description,
      file_links: submissionData.fileLinks.split('\n').filter(l => l.trim()),
      voting_closes_at: closeDate.toISOString(),
      status: 'pending'
    });

    if (error) {
      alert('Error submitting. Please try again.');
    } else {
      setShowSuccess(true);
      setTimeout(() => {
        setShowSuccess(false);
        setView('submissions');
        setSelectedModule(null);
        setSubmissionStep(0);
        fetchData();
      }, 2500);
    }
  }

  async function castVote(submissionId, vote) {
    if (!profile || profile.stake <= 0) return alert("You need stake to vote.");

    const { error } = await supabase.from('votes').insert({
      submission_id: submissionId,
      user_id: session.user.id,
      vote: vote,
      stake_at_vote: profile.stake
    });

    if (error) {
      if(error.code === '23505') alert("You already voted on this.");
      else alert("Error voting.");
    } else {
      fetchData();
    }
  }

  // --- HELPERS ---
  const modulesByPhase = modules.reduce((acc, m) => {
    if (!acc[m.phase]) acc[m.phase] = [];
    acc[m.phase].push(m);
    return acc;
  }, {});

  const togglePhase = (p) => setExpandedPhases(prev => prev.includes(p) ? prev.filter(x => x !== p) : [...prev, p]);

  const pendingCount = submissions.filter(s => s.status === 'pending' && new Date(s.voting_closes_at) > new Date()).length;

  const totalStake = contributors.reduce((sum, c) => sum + Number(c.stake), 0);

  if (loading) return <div style={{...styles.container, display:'flex', justifyContent:'center', alignItems:'center'}}>Loading...</div>;

  return (
    <div style={styles.container}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=Manrope:wght@400;700&display=swap');`}</style>

      {/* HEADER */}
      <header style={styles.header}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', maxWidth: '800px', margin: '0 auto' }}>
          <div style={{ cursor: 'pointer' }} onClick={() => setView('about')}>
            <h1 style={{ fontSize: '1.5rem', fontWeight: 700, margin: 0 }}>Mouthful of River</h1>
            <p style={{ fontSize: '0.75rem', color: colors.textLight, margin: '0.1rem 0 0 0' }}>Open-source documentary</p>
          </div>
          <nav style={{ display: 'flex', gap: '1rem', alignItems: 'center' }}>
            <button onClick={() => setView('about')} style={styles.navBtn(view === 'about')}>About</button>
            <button onClick={() => setView('contribute')} style={styles.navBtn(view === 'contribute' || view === 'module-detail' || view === 'submit')}>Contribute</button>
            <button onClick={() => setView('submissions')} style={styles.navBtn(view === 'submissions')}>
              Vote {pendingCount > 0 && <span style={{background: colors.accent, padding: '0 5px', borderRadius: '4px', fontSize: '0.7rem'}}>{pendingCount}</span>}
            </button>
            <button onClick={() => setView('contributors')} style={styles.navBtn(view === 'contributors')}>Stakes</button>
            <button onClick={() => setView('governance')} style={styles.navBtn(view === 'governance')}>Governance</button>

            {session ? (
               <div style={{marginLeft: '0.5rem', fontSize: '0.8rem', cursor: 'pointer', color: colors.textLight}} onClick={signOut}>Sign Out</div>
            ) : (
               <button onClick={signInWithGoogle} style={{...styles.navBtn(false), color: colors.accentBlue, fontWeight: 700}}>Sign In</button>
            )}
          </nav>
        </div>
      </header>

      {/* MAIN CONTENT */}
      <main style={{ padding: '2rem', maxWidth: '800px', margin: '0 auto' }}>

        {/* ABOUT VIEW */}
        {view === 'about' && (
          <div>
            <h2 style={{ fontSize: '1.4rem', fontWeight: 700, lineHeight: 1.4, marginBottom: '1rem' }}>
              AI gives rivers a voice—but the data centers powering that voice threaten to drain them dry.
            </h2>
            <p style={{ fontSize: '1rem', lineHeight: 1.7, marginBottom: '2rem' }}>
              <em>Mouthful of River</em> is a mosaic documentary following scientists, indigenous communities, and activists searching for ways to understand: what does the river truly want?
            </p>

            <div style={{ borderLeft: `4px solid ${colors.accent}`, padding: '1rem 1.25rem', marginBottom: '2rem', background: 'rgba(253, 184, 19, 0.08)' }}>
              <h3 style={{ fontSize: '1rem', fontWeight: 700, marginBottom: '0.5rem' }}>An open-source film</h3>
              <p style={{ fontSize: '0.9rem', lineHeight: 1.7, margin: 0 }}>
                Anyone can contribute. If your contribution is approved, you earn voting rights and a share of the profits. All material is licensed CC0.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: 'repeat(4, 1fr)', gap: '2px', background: colors.border, marginBottom: '2rem' }}>
              {Object.entries(phaseConfig).map(([name, conf]) => (
                <div key={name} style={{ padding: '0.75rem', background: colors.bg, textAlign: 'center' }}>
                  <div style={{ fontSize: '1.25rem', fontWeight: 700 }}>{conf.budget}</div>
                  <div style={{ fontSize: '0.7rem', color: colors.textLight }}>{name}</div>
                </div>
              ))}
            </div>

            <button onClick={() => setView('contribute')} style={styles.btnPrimary}>See open contributions →</button>
          </div>
        )}

        {/* CONTRIBUTE VIEW */}
        {view === 'contribute' && (
          <div>
             <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1.5rem' }}>Contribution modules</h2>
             {Object.keys(phaseConfig).map(phase => {
               const modulesInPhase = modulesByPhase[phase] || [];
               const isExpanded = expandedPhases.includes(phase);
               return (
                 <div key={phase} style={{marginBottom: isExpanded ? '1rem' : '0.5rem'}}>
                   <button onClick={() => togglePhase(phase)} style={styles.phaseHeader(isExpanded)}>
                      <div style={{flex: 1}}>
                        <div style={{fontWeight: 700}}>{phase}</div>
                        <div style={{fontSize: '0.75rem', color: colors.textLight}}>Budget: {phaseConfig[phase].budget}</div>
                      </div>
                      <div style={{fontSize: '1.2rem'}}>{isExpanded ? '-' : '+'}</div>
                   </button>
                   {isExpanded && (
                     <div style={{border: `2px solid ${colors.border}`, borderTop: 'none', padding: '0.75rem', display: 'grid', gap: '0.5rem'}}>
                       {modulesInPhase.map(m => (
                         <div key={m.id} onClick={() => m.status !== 'locked' && setSelectedModule(m) & setView('module-detail')} style={styles.moduleCard(m.status === 'locked')}>
                           <div style={{fontSize: '1.5rem'}}>{typeIcons[m.type] || '📄'}</div>
                           <div style={{flex: 1}}>
                             <div style={{fontWeight: 700, fontSize: '0.95rem'}}>{m.title}</div>
                             <div style={{fontSize: '0.8rem', color: colors.textLight}}>{m.status === 'locked' ? `Locked: ${m.prerequisite}` : m.description.substring(0, 100) + '...'}</div>
                           </div>
                           <div style={{textAlign: 'right'}}>
                             <div style={{fontWeight: 700}}>{m.stake}%</div>
                             <div style={{fontSize: '0.7rem'}}>stake</div>
                           </div>
                         </div>
                       ))}
                       {modulesInPhase.length === 0 && <div style={{fontStyle:'italic', fontSize:'0.9rem', color: colors.textLight}}>No modules yet.</div>}
                     </div>
                   )}
                 </div>
               )
             })}
          </div>
        )}

        {/* MODULE DETAIL VIEW */}
        {view === 'module-detail' && selectedModule && (
          <div>
            <button onClick={() => setView('contribute')} style={{background:'none', border:'none', cursor:'pointer', marginBottom:'1rem'}}>← Back</button>
            <div style={{border: `2px solid ${colors.border}`, padding: '1.5rem'}}>
              <div style={{fontSize: '0.8rem', color: colors.textLight, textTransform: 'uppercase', marginBottom:'0.5rem'}}>{selectedModule.type}</div>
              <h2 style={{fontSize: '1.5rem', fontWeight: 700, marginBottom: '1rem'}}>{selectedModule.title}</h2>
              <p style={{lineHeight: 1.7, marginBottom: '1.5rem'}}>{selectedModule.description}</p>

              <div style={{background: 'rgba(253, 184, 19, 0.1)', padding: '1rem', marginBottom: '1.5rem'}}>
                 <div style={{fontWeight: 700, marginBottom: '0.5rem'}}>Rewards</div>
                 <div style={{display: 'flex', gap: '2rem'}}>
                    <div><span style={{fontWeight: 700, fontSize: '1.2rem'}}>{selectedModule.stake}%</span> <br/><span style={{fontSize:'0.8rem'}}>Voting Power</span></div>
                    <div><span style={{fontWeight: 700, fontSize: '1.2rem'}}>{selectedModule.stake}%</span> <br/><span style={{fontSize:'0.8rem'}}>Profit Share</span></div>
                 </div>
              </div>

              {session ? (
                <button onClick={() => setView('submit')} style={styles.btnPrimary}>Submit Contribution</button>
              ) : (
                <button onClick={signInWithGoogle} style={{...styles.btnPrimary, background: colors.accentBlue, color: 'white'}}>Sign In to Contribute</button>
              )}
            </div>
          </div>
        )}

        {/* SUBMIT VIEW */}
        {view === 'submit' && selectedModule && (
          <div>
            <button onClick={() => setView('module-detail')} style={{background:'none', border:'none', cursor:'pointer', marginBottom:'1rem'}}>← Back</button>
            <div style={{border: `2px solid ${colors.border}`, padding: '2rem'}}>
              <h3 style={{marginTop: 0}}>Step {submissionStep + 1} of 3</h3>

              {submissionStep === 0 && (
                <div>
                  <p>Paste links to your files (Google Drive, Dropbox, etc), one per line:</p>
                  <textarea
                    style={{width: '100%', height: '100px', padding: '0.5rem', fontFamily: 'inherit'}}
                    value={submissionData.fileLinks}
                    onChange={e => setSubmissionData({...submissionData, fileLinks: e.target.value})}
                  />
                  <div style={{marginTop: '1rem'}}>
                    <button onClick={() => setSubmissionStep(1)} style={styles.btnPrimary}>Next</button>
                  </div>
                </div>
              )}

              {submissionStep === 1 && (
                <div>
                  <p>Describe your contribution:</p>
                  <textarea
                    style={{width: '100%', height: '100px', padding: '0.5rem', fontFamily: 'inherit'}}
                    value={submissionData.description}
                    onChange={e => setSubmissionData({...submissionData, description: e.target.value})}
                  />
                  <div style={{marginTop: '1rem', display: 'flex', gap: '1rem'}}>
                    <button onClick={() => setSubmissionStep(0)} style={{...styles.btnPrimary, background: '#eee'}}>Back</button>
                    <button onClick={() => setSubmissionStep(2)} style={styles.btnPrimary}>Next</button>
                  </div>
                </div>
              )}

              {submissionStep === 2 && (
                <div>
                  <p>Confirm submission for <strong>{selectedModule.title}</strong>.</p>
                  <p style={{fontSize: '0.9rem', color: colors.textLight}}>By submitting, you agree to license your work under CC0.</p>
                  <div style={{marginTop: '1rem', display: 'flex', gap: '1rem'}}>
                    <button onClick={() => setSubmissionStep(1)} style={{...styles.btnPrimary, background: '#eee'}}>Back</button>
                    <button onClick={submitContribution} style={styles.btnPrimary}>Submit for Review</button>
                  </div>
                </div>
              )}
            </div>
          </div>
        )}

        {/* SUBMISSIONS / VOTE VIEW */}
        {view === 'submissions' && (
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1.5rem' }}>Pending Votes</h2>
            {submissions.filter(s => s.status === 'pending').length === 0 && <p>No pending votes.</p>}

            <div style={{display: 'grid', gap: '1rem'}}>
              {submissions.filter(s => s.status === 'pending').map(sub => {
                const hasVoted = sub.votes.some(v => v.user_id === session?.user?.id);
                const yesVotes = sub.votes.filter(v => v.vote === 'yes').reduce((acc, v) => acc + v.stake_at_vote, 0);
                const noVotes = sub.votes.filter(v => v.vote === 'no').reduce((acc, v) => acc + v.stake_at_vote, 0);
                const totalVoted = yesVotes + noVotes;
                const yesPercent = totalVoted > 0 ? Math.round((yesVotes/totalVoted)*100) : 0;

                return (
                  <div key={sub.id} style={{border: `1px solid ${colors.borderLight}`, padding: '1rem', background: 'white'}}>
                    <div style={{fontWeight: 700}}>{sub.module.title}</div>
                    <div style={{fontSize: '0.8rem', color: colors.textLight, marginBottom: '0.5rem'}}>by {sub.user?.name || 'Contributor'}</div>
                    <p style={{background: '#f9f9f9', padding: '0.5rem', fontSize: '0.9rem'}}>{sub.description}</p>

                    {/* Fixed: Only show View Files link if file_links exists and has items */}
                    {sub.file_links && sub.file_links.length > 0 && (
                      <div style={{fontSize: '0.8rem', marginBottom: '1rem'}}>
                        {sub.file_links.map((link, index) => (
                          <a key={index} href={link} target="_blank" rel="noreferrer" style={{color: colors.accentBlue, marginRight: '1rem'}}>
                            View File {sub.file_links.length > 1 ? index + 1 : ''}
                          </a>
                        ))}
                      </div>
                    )}

                    <div style={{marginBottom: '1rem'}}>
                      <div style={{fontSize: '0.8rem', fontWeight: 700}}>Current Vote: {yesPercent}% Yes</div>
                      <div style={{height: '6px', background: '#eee', marginTop: '4px'}}>
                        <div style={{height: '100%', width: `${yesPercent}%`, background: colors.accent}} />
                      </div>
                    </div>

                    {session && profile?.stake > 0 && !hasVoted && (
                      <div style={{display: 'flex', gap: '0.5rem'}}>
                        <button onClick={() => castVote(sub.id, 'yes')} style={{...styles.btnPrimary, padding: '0.5rem', fontSize: '0.8rem'}}>Approve</button>
                        <button onClick={() => castVote(sub.id, 'no')} style={{...styles.btnPrimary, background: '#eee', padding: '0.5rem', fontSize: '0.8rem'}}>Reject</button>
                      </div>
                    )}
                    {hasVoted && <div style={{fontSize:'0.8rem', color: colors.textLight}}>You have voted.</div>}
                  </div>
                )
              })}
            </div>
          </div>
        )}

        {/* GOVERNANCE VIEW */}
        {view === 'governance' && (
          <div>
            <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1.5rem' }}>
              How decisions are made
            </h2>

            <div style={{ display: 'grid', gap: '2px', background: colors.border }}>
              <div style={{ padding: '1rem', background: colors.bg }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 0.4rem 0' }}>Voting power</h4>
                <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: colors.textLight, margin: 0 }}>
                  <strong style={{ color: colors.text }}>Stake = voting share.</strong> If you hold 10% stake, your vote counts for 10% of the total.
                </p>
              </div>

              <div style={{ padding: '1rem', background: colors.bg }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 0.4rem 0' }}>Approving contributions</h4>
                <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: colors.textLight, margin: 0 }}>
                  When you submit a contribution, all current stakeholders vote. Approval requires <strong style={{ color: colors.text }}>majority stake</strong>.
                </p>
              </div>

              <div style={{ padding: '1rem', background: colors.bg }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 0.4rem 0' }}>Adding new modules</h4>
                <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: colors.textLight, margin: 0 }}>
                  Small modules (≤2% stake) can be added by <strong style={{ color: colors.text }}>any stakeholder holding 10%+</strong>. Larger modules require a vote.
                </p>
              </div>

              <div style={{ padding: '1rem', background: colors.bg }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 0.4rem 0' }}>Licensing & forking</h4>
                <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: colors.textLight, margin: 0 }}>
                  All contributed material is licensed <strong style={{ color: colors.text }}>CC0</strong>. Anyone can fork this project with credit.
                </p>
              </div>

              <div style={{ padding: '1rem', background: colors.bg }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 0.4rem 0' }}>Profit distribution</h4>
                <p style={{ fontSize: '0.9rem', lineHeight: 1.6, color: colors.textLight, margin: 0 }}>
                  Stake represents your share of the <strong style={{ color: colors.text }}>contributor pool</strong>. Profits are distributed by stake.
                </p>
              </div>

              <div style={{ padding: '1rem', background: colors.bg }}>
                <h4 style={{ fontSize: '0.95rem', fontWeight: 700, margin: '0 0 0.4rem 0' }}>Phase budgets</h4>
                <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, 1fr)', gap: '0.25rem', marginTop: '0.5rem' }}>
                  {Object.entries(phaseConfig).map(([name, conf]) => (
                    <div key={name} style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.85rem' }}>
                      <span style={{ color: colors.textLight }}>{name}</span>
                      <span style={{ fontWeight: 700 }}>{conf.budget}</span>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          </div>
        )}

        {/* CONTRIBUTORS VIEW */}
        {view === 'contributors' && (
           <div>
             <h2 style={{ fontSize: '1.1rem', fontWeight: 700, marginBottom: '1rem' }}>Current Stakes</h2>
             <div style={{ display: 'flex', height: '32px', border: `2px solid ${colors.border}`, marginBottom: '2rem' }}>
                {contributors.map((c, i) => (
                  <div key={c.id} style={{
                    width: `${(c.stake / totalStake) * 100}%`,
                    background: i % 2 === 0 ? colors.accent : '#e0c370',
                    borderRight: i < contributors.length - 1 ? `1px solid ${colors.border}` : 'none',
                    display: 'flex', alignItems: 'center', justifyContent: 'center', fontSize: '0.8rem', fontWeight: 700
                  }}>
                    {c.stake}%
                  </div>
                ))}
             </div>
             <div style={{borderTop: `1px solid ${colors.borderLight}`}}>
                {contributors.map(c => (
                  <div key={c.id} style={{display: 'flex', justifyContent:'space-between', padding: '1rem 0', borderBottom: `1px solid ${colors.borderLight}`}}>
                    <div>
                      <div style={{fontWeight: 700}}>{c.name}</div>
                      <div style={{fontSize: '0.8rem', color: colors.textLight}}>{c.role}</div>
                    </div>
                    <div style={{fontWeight: 700, fontSize: '1.2rem'}}>{c.stake}%</div>
                  </div>
                ))}
             </div>
           </div>
        )}

        {/* SUCCESS MESSAGE */}
        {showSuccess && (
          <div style={{position:'fixed', top:0, left:0, right:0, bottom:0, background:'rgba(255,255,255,0.95)', display:'flex', alignItems:'center', justifyContent:'center', zIndex: 100}}>
             <div style={{textAlign:'center'}}>
               <h2 style={{fontSize:'2rem'}}>Submission Received!</h2>
               <p>Stakeholders have 14 days to vote.</p>
             </div>
          </div>
        )}
      </main>
    </div>
  );
}
