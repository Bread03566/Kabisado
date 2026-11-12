// The API returns one message per problem; point it at the form field it is about.
export function fieldForError(err) {
  const msg = (err.message || '').toLowerCase();
  if (err.status === 409 || msg.includes('username')) return 'username';
  if (msg.includes('display')) return 'displayName';
  if (msg.includes('password')) return err.status === 401 ? 'form' : 'password';
  return 'form';
}
