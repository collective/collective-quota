import React from 'react';
import { useSelector } from 'react-redux';
import { Link } from 'react-router-dom';
import { Plug } from '@plone/volto/components/manage/Pluggable';
import Icon from '@plone/volto/components/theme/Icon/Icon';
import rightArrowSVG from '@plone/volto/icons/right-key.svg';

// "Disk usage" in the personal tools menu, shown only when the backend lists
// the `disk-usage` user action (it checks the permission).
const UserMenuEntry = () => {
  const token = useSelector((state) => state.userSession?.token);
  const action = useSelector((state) =>
    state.actions?.actions?.user?.find((item) => item.id === 'disk-usage'),
  );
  if (!token || !action) return null;
  return (
    <Plug pluggable="toolbar-user-menu" id="collective-quota-disk-usage">
      <li>
        <Link id="collective-quota-disk-usage" to="/quota-usage">
          {action.title}
          <Icon name={rightArrowSVG} size="24px" />
        </Link>
      </li>
    </Plug>
  );
};

export default UserMenuEntry;
