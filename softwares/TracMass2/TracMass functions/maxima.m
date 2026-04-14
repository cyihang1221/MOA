function [m,ndx] = maxima(x,varargin)
%[m,ndx] = maxima(x)
% find local maxima of x
% find the places where diff(x) changes sign
% checks x(1) and x(end) as well

%by: Magnus Åberg
d = diff(x);
m = []; ndx = [];
if numel(x)==0,
   return
end
if numel(x)==1;
   m=x; ndx=1;
   return
end
if x(1)> x(2)
   m(1)   = x(1);
   ndx(1) = 1;
end

for i = 1:length(d)-1
   if d(i) > 0 && d(i)*d(i+1) <= 0
      m(end+1)   = x(i+1);
      ndx(end+1) = i+1;
   end
end

if x(end) > x(end-1),
   m(end+1) = x(end);
   ndx(end+1) = length(x);
end

m = m(:); % column vector
ndx = ndx(:);


[m, ordr] = sort(m,1,'descend');
ndx = ndx(ordr);

if nargin>1,
   qualifiers = varargin(1:2:end);
   values     = varargin(2:2:end);
   for i = 1:numel(qualifiers);
      switch (qualifiers{i})
         case 'minDistance'
            minDist = values{i};
            D = outerDifference(ndx,ndx);
            del_mask = false(1,numel(ndx));
            for c = 1:numel(ndx),
               if del_mask(c), continue, end
               for r = c+1:numel(ndx);
                  %fprintf(1,'%3i %3i - %6i %6i - %9.0f %9.0f - %6i\n',[c, r, ndx([c r])'  m([c r])' D(r,c)])
                  if (abs(D(r,c)) < minDist) && ~del_mask(c),
                     del_mask(r) = true;
                  end
               end
            end
            m(del_mask) =[];
            ndx(del_mask) = [];
      end
   end
end

%disp('maxima')
%keyboard

