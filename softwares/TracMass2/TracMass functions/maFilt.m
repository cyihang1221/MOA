function Z=maFilt(X,f)
% Z = maFilt(X,f)
% wrapper for conv (builtin)
% truncates the conv result to the same size as X;
% INPUT:
% X - samples as columns
% f - filter (odd number of elements required)
% OUTPUT:
% Z - filtered output same size as X.
%
% Magnus Åberg 2008-12-02.
% new version with padding removes edge effects /MÅ 2009-09-28
[r,c] = size(X);
l = numel(f);
h=floor(l/2);
assert(isOdd(l));
Z = zeros(r+l-1+2*h,c);
for i  = 1:c,
   foo = [X(1,i)*ones(h,1); X(:,i); X(end,i)*ones(h,1)];
   Z(:,i) = conv(foo,f);
end
%Z =Z'; - BUG 2010-05-28
%Z = Z(2*h+1:end-2*h)'; - BUG 2010-05-28
Z =  Z(2*h+1:end-2*h,:); % BUG-fix 2010-05-28
%Z =Z';

